"""External Expo builds: per-project sources and products, shared Linux toolchain."""

import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
from .config import SCRIPTS
from . import signing
from pathlib import Path


def run(args, cwd, log, env=None):
    print(f"{log.stem}: {log}", flush=True)

    with log.open("w") as stream:
        result = subprocess.run(
            list(map(str, args)),
            cwd=cwd,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )

    if result.returncode:
        raise ValueError(f"Step {log.stem} failed; see {log}")


def build_directory(config, source):
    source = source.resolve()

    if not (source / "package.json").is_file():
        raise ValueError("The Expo project must contain package.json.")

    # Identity derives from the full path; equal folder names cannot share artifacts.
    key = (
        re.sub(r"[^a-zA-Z0-9_-]", "-", source.name)
        + "-"
        + hashlib.sha256(str(source).encode()).hexdigest()[:10]
    )

    job = config.cache / "expo" / key

    if source == job or source.is_relative_to(job) or job.is_relative_to(source):
        raise ValueError("The source must be outside the build directory.")

    return job


def tool_env(config, project, build):
    tools = config.toolchain

    env = dict(
        config.env(),
        CI="1",
        NODE_ENV="production",
        IOS_LINUX_PROJECT=str(project),
        IOS_LINUX_BUILD=str(build),
        COCOAPODS_DISABLE_STATS="true",
    )

    env.update(
        LD_LIBRARY_PATH=str(tools / "ruby/usr/lib/x86_64-linux-gnu"),
        RUBYLIB=":".join(
            str(tools / p)
            for p in [
                "ruby/usr/lib/ruby/3.2.0",
                "ruby/usr/lib/x86_64-linux-gnu/ruby/3.2.0",
                "ruby/usr/lib/ruby/vendor_ruby",
            ]
        ),
        GEM_HOME=str(tools / "gems"),
        GEM_PATH=":".join(
            str(tools / p)
            for p in [
                "gems",
                "ruby/usr/share/rubygems-integration/all",
                "ruby/usr/lib/ruby/gems/3.2.0",
            ]
        ),
        PATH=":".join(
            [
                str(SCRIPTS / "bin"),
                str(tools / "gems/bin"),
                str(tools / "swift/usr/bin"),
                os.environ["PATH"],
            ]
        ),
    )

    return env


def tools_ruby(config):
    return config.toolchain / "ruby/usr/bin/ruby3.2"


def prepare(config, source):
    job = build_directory(config, source)
    project, build = job / "project", job / "build"
    build.mkdir(parents=True, exist_ok=True)
    # Replace sources while keeping caches that belong only to this project path.
    caches = ["node_modules", "ios/Pods", "ios/Podfile.lock"]

    for name in caches:
        cached = job / ("cache-" + name.replace("/", "-"))

        if (project / name).exists():
            if cached.exists():
                raise ValueError("Cache recovery required: " + str(cached))

            (project / name).rename(cached)

    if project.exists():
        shutil.rmtree(project)

    shutil.copytree(
        source,
        project,
        ignore=shutil.ignore_patterns(".git", "node_modules", ".expo", ".gradle", "Pods", "build"),
    )

    for name in caches:
        cached = job / ("cache-" + name.replace("/", "-"))

        if cached.exists():
            (project / name).parent.mkdir(parents=True, exist_ok=True)

            if (project / name).is_file():
                (project / name).unlink()

            cached.rename(project / name)

    env = tool_env(config, project, build)
    lock = project / "package-lock.json"

    if not lock.is_file():
        raise ValueError(
            "This backend requires package-lock.json to install the project dependency versions."
        )

    fingerprint = hashlib.sha256(
        lock.read_bytes() + (project / "package.json").read_bytes()
    ).hexdigest()

    stamp = job / "dependencies.sha256"

    if (
        not (project / "node_modules/expo/package.json").exists()
        or not stamp.exists()
        or stamp.read_text() != fingerprint
    ):
        run(
            ["npm", "ci", "--include=dev", "--no-audit", "--no-fund"],
            project,
            job / "npm-install.log",
            env,
        )

        stamp.write_text(fingerprint)

    run(
        [
            "node",
            "node_modules/expo/bin/cli",
            "prebuild",
            "--platform",
            "ios",
            "--no-install",
        ],
        project,
        job / "prebuild.log",
        env,
    )

    podfile = project / "ios/Podfile"
    text = podfile.read_text()
    marker = "require 'json'"

    if marker not in text:
        raise ValueError("Unrecognized Podfile: Linux configuration insertion point not found.")

    text = text.replace(
        marker,
        "# Linux resolves pods; the separate compiler uses the Apple SDK.\nclass ::ReactNativePodsUtils\n  def self.check_minimum_required_xcode(**_options); end\nend\n"
        + marker,
        1,
    )

    podfile.write_text(text)

    run(
        [tools_ruby(config), config.toolchain / "gems/bin/pod", "install"],
        project / "ios",
        job / "pod-install.log",
        env,
    )

    tools = config.toolchain

    for filename, xcode in [
        ("pods-graph.json", project / "ios/Pods/Pods.xcodeproj"),
        ("app-graph.json", next((project / "ios").glob("*.xcodeproj"))),
    ]:
        # Exporter resolves paths from the actual project, not another app's graph.
        with (build / filename).open("w") as stream:
            subprocess.run(
                [
                    str(tools / "ruby/usr/bin/ruby3.2"),
                    str(SCRIPTS / "export-project.rb"),
                    str(xcode),
                ],
                env=env,
                stdout=stream,
                check=True,
            )

    return job


def graphs(job):
    build = job / "build"

    return json.loads((build / "pods-graph.json").read_text()), json.loads(
        (build / "app-graph.json").read_text()
    )


def target_kind(target):
    kind = target.get("product_type")
    if kind == "com.apple.product-type.application":
        return "app"
    if kind == "com.apple.product-type.app-extension":
        return "extension"
    if kind is None:  # Graphs exported by older versions.
        return "extension" if target["settings"].get("APPLICATION_EXTENSION_API_ONLY") == "YES" else "app"
    raise ValueError("Unsupported product type for " + target["name"] + ": " + kind)


def target_plan(apps):
    mains = [t for t in apps if target_kind(t) == "app"]
    if len(mains) != 1:
        raise ValueError("Expected exactly one application and zero or more app extensions.")
    names = [t["name"] for t in apps]
    if len(set(names)) != len(names) or any(Path(n).name != n or n in (".", "..") for n in names):
        raise ValueError("Target names must be unique path components.")
    return mains[0], [t for t in apps if target_kind(t) == "extension"]


def target_dependencies(libraries, app):
    by_name = {t["name"]: t for t in libraries}
    result, visited, active = [], set(), set()
    def visit(name):
        if name in active:
            raise ValueError("Cyclic CocoaPods dependency: " + name)
        if name in visited:
            return
        if name not in by_name:
            raise ValueError("Missing CocoaPods target: " + name)
        active.add(name)
        target = by_name[name]
        for dependency in target.get("dependencies", []):
            visit(dependency)
        active.remove(name)
        visited.add(name)
        result.append(target)
    visit("Pods-" + app["name"])
    return result


def bundle_widgets(config, job):
    project, build = job / "project", job / "build"
    libraries, apps = graphs(job)
    target_plan(apps)
    if not any(t["name"] == "ExpoWidgets" for t in libraries):
        return
    package = project / "node_modules/expo-widgets"
    output = build / "app-resources/ExpoWidgets.bundle"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir()
    env = dict(tool_env(config, project, build), EXPO_OVERRIDE_METRO_CONFIG=str(package / "metro.config.js"))
    run(["node", project / "node_modules/expo/bin/cli", "export:embed", "--platform", "ios",
         "--bundle-output", output / "ExpoWidgets.bundle", "--entry-file", package / "bundle/index.ts",
         "--dev", "false", "--skip-server"], project, job / "widgets.log", env)
    (output / "Info.plist").write_bytes(plistlib.dumps({
        "CFBundleIdentifier": "org.cocoapods.ExpoWidgets", "CFBundleName": "ExpoWidgets",
        "CFBundlePackageType": "BNDL", "CFBundleVersion": "1"}))


def constants_script(project):
    # npm can nest Expo's dependencies instead of hoisting them to the app root.
    return (
        Path(
            subprocess.check_output(
                [
                    "node",
                    "-e",
                    "console.log(require.resolve('expo-constants/package.json', {paths: [process.cwd(), require.resolve('expo/package.json')]}))",
                ],
                cwd=project,
                text=True,
            ).strip()
        ).parent
        / "scripts/getAppConfig.js"
    )


def bundle(config, job):
    project, build = job / "project", job / "build"
    modules = project / "node_modules"
    env = tool_env(config, project, build)
    resources = build / "app-resources"

    if resources.exists():
        shutil.rmtree(resources)

    resources.mkdir()

    entry = (
        subprocess.check_output(
            [
                "node",
                "-e",
                "require('expo/scripts/resolveAppEntry')",
                str(project),
                "ios",
                "absolute",
            ],
            cwd=project,
            env=env,
            text=True,
        )
        .strip()
        .splitlines()[-1]
    )

    run(
        [
            "node",
            modules / "expo/bin/cli",
            "export:embed",
            "--platform",
            "ios",
            "--dev",
            "false",
            "--entry-file",
            entry,
            "--bundle-output",
            resources / "main.jsbundle",
            "--assets-dest",
            resources,
        ],
        project,
        job / "bundle.log",
        env,
    )

    compilers = [
        modules / "hermes-compiler/hermesc/linux64-bin/hermesc",
        modules / "react-native/sdks/hermesc/linux64-bin/hermesc",
    ]

    compiler = next((p for p in compilers if p.is_file()), None)

    if compiler is None:
        raise ValueError("A matching Linux Hermes compiler for this project was not found.")

    run(
        [
            compiler,
            "-O",
            "-emit-binary",
            "-out",
            resources / "main.hbc",
            resources / "main.jsbundle",
        ],
        project,
        job / "hermes.log",
        env,
    )

    (resources / "main.hbc").replace(resources / "main.jsbundle")
    constants = resources / "EXConstants.bundle"
    constants.mkdir()

    run(
        ["node", constants_script(project), project, constants],
        project,
        job / "constants.log",
        env,
    )

    updates = modules / "expo-updates/utils/build/createUpdatesResources.js"

    if updates.exists():
        dest = resources / "EXUpdates.bundle"
        dest.mkdir()

        run(
            ["node", updates, "ios", project, dest, "all", entry],
            project,
            job / "updates.log",
            env,
        )


def patch_splash(project):
    path = project / "node_modules/expo-splash-screen/ios/SplashScreenManager.swift"

    if not path.exists():
        return

    text = path.read_text()

    if 'ofType: "storyboardc"' in text:
        return

    marker = "    if let vc = UIStoryboard(name: splashScreenFilename, bundle: nil).instantiateInitialViewController() {"

    if marker not in text:
        raise ValueError("Unrecognized splash screen implementation for the Linux build.")

    # shortcut: no ibtool on Linux; use UIKit launch resources until storyboard compilation is supported.
    text = text.replace(
        marker,
        '    guard Bundle.main.path(forResource: splashScreenFilename, ofType: "storyboardc") != nil else { return }\n'
        + marker,
    )

    path.write_text(text)


def patch_native_sources(project):
    patch_splash(project)
    source = project / "node_modules/react-native-screens/ios/RNSScreenStackHeaderConfig.mm"

    if source.exists():
        text = source.read_text()

        # shortcut: upstream Clang lacks Apple's constexpr boxed literals; keep the same immutable values.
        for name, value in [
            ("DEFAULT_TITLE_FONT_SIZE", 17),
            ("DEFAULT_TITLE_LARGE_FONT_SIZE", 34),
        ]:
            text = text.replace(
                f"static constexpr auto {name} = @{value};",
                f"static const auto {name} = @{value};",
            )

        if text != source.read_text():
            source.write_text(text)


def patch_scene(project, apps):
    # SDK 27 requires scene-owned windows; adapt only the standard Expo template.
    for app in apps:
        path = project / "ios" / app["name"] / "AppDelegate.swift"
        text = path.read_text()

        if "UIWindowSceneDelegate" in text:
            continue

        start = text.find("    window = UIWindow(frame: UIScreen.main.bounds)")
        end = text.find("      launchOptions: launchOptions)", start)

        if start < 0 or end < 0:
            raise ValueError(
                "Custom AppDelegate: adapt the UIScene lifecycle before building with SDK 27."
            )

        text = text[:start] + text[end + len("      launchOptions: launchOptions)") :]

        text += """
class SceneDelegate: UIResponder, UIWindowSceneDelegate {
  var window: UIWindow?
  private var appDelegate: AppDelegate { UIApplication.shared.delegate as! AppDelegate }
  func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options options: UIScene.ConnectionOptions) {
    guard let scene = scene as? UIWindowScene else { return }
    let window = UIWindow(windowScene: scene)
    self.window = window
    appDelegate.window = window
    var launchOptions: [UIApplication.LaunchOptionsKey: Any] = [:]
    if let context = options.urlContexts.first { launchOptions[.url] = context.url }
    appDelegate.reactNativeFactory?.startReactNative(withModuleName: "main", in: window, launchOptions: launchOptions)
    for activity in options.userActivities { self.scene(scene, continue: activity) }
  }
  func scene(_ scene: UIScene, openURLContexts contexts: Set<UIOpenURLContext>) {
    for context in contexts {
      _ = appDelegate.application(UIApplication.shared, open: context.url, options: [
        .sourceApplication: context.options.sourceApplication as Any,
        .annotation: context.options.annotation as Any,
        .openInPlace: context.options.openInPlace
      ])
    }
  }
  func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
    _ = appDelegate.application(UIApplication.shared, continue: userActivity, restorationHandler: { _ in })
  }
  func sceneDidBecomeActive(_ scene: UIScene) { appDelegate.applicationDidBecomeActive(UIApplication.shared) }
  func sceneWillResignActive(_ scene: UIScene) { appDelegate.applicationWillResignActive(UIApplication.shared) }
  func sceneWillEnterForeground(_ scene: UIScene) { appDelegate.applicationWillEnterForeground(UIApplication.shared) }
  func sceneDidEnterBackground(_ scene: UIScene) { appDelegate.applicationDidEnterBackground(UIApplication.shared) }
}
"""

        path.write_text(text)


def native(config, job):
    project, build = job / "project", job / "build"
    pods = project / "ios/Pods"
    env = tool_env(config, project, build)
    patch_native_sources(project)
    libraries, apps = graphs(job)

    main, _ = target_plan(apps)
    patch_scene(project, [main])

    rn = project / "node_modules/react-native"
    version = json.loads((rn / "package.json").read_text())["version"]

    for script in [
        "scripts/replace-rncore-version.js",
        "third-party-podspecs/replace_dependencies_version.js",
        "sdks/hermes-engine/utils/replace_hermes_version.js",
    ]:
        if (rn / script).exists():
            artifact_version = version
            if script.endswith("replace_hermes_version.js"):
                # Recent RN releases version Hermes independently of React Native.
                spec = json.loads((pods / "Local Podspecs/hermes-engine.podspec.json").read_text())
                artifact_version = spec["version"]
                archive = pods / "hermes-engine-artifacts" / ("hermes-ios-" + artifact_version + "-release.tar.gz")
                if not archive.is_file():
                    raise ValueError("Missing resolved Release Hermes archive: " + str(archive))
                if not [fw for fw in (pods / "hermes-engine").rglob("ios-arm64/*.framework") if (fw / fw.stem).is_file()]:
                    (pods / ".last_build_configuration").unlink(missing_ok=True)
            run(
                ["node", rn / script, "-c", "Release", "-r", artifact_version, "-p", pods],
                pods,
                job / (Path(script).stem + ".log"),
                env,
            )

    if (rn / "sdks/hermes-engine/utils/replace_hermes_version.js").exists() and not [fw for fw in (pods / "hermes-engine").rglob("ios-arm64/*.framework") if (fw / fw.stem).is_file()]:
        raise ValueError("Hermes Release extraction did not produce a framework.")

    products = build / "products"

    if products.exists():
        shutil.rmtree(products)

    products.mkdir()

    for cached in ["headers"]:
        if (build / cached).exists():
            shutil.rmtree(build / cached)

    common = build / "headers/common"
    common.mkdir(parents=True, exist_ok=True)

    for target in libraries:
        out = products / target["name"]
        out.mkdir(exist_ok=True)
        support = pods / "Target Support Files" / target["name"]
        module = target["settings"].get("PRODUCT_MODULE_NAME") or target["name"]

        for source in support.glob("*.modulemap"):
            shutil.copy2(source, out / (module + ".modulemap"))

            for header in support.glob("*.h"):
                shutil.copy2(header, out / header.name)

        for header in target["headers"]:
            src = Path(header["path"])
            dest = common / src.name

            if not dest.exists() and not dest.is_symlink():
                dest.symlink_to(src)

    # Reproduce Xcode's flat public-header lookup for vendored frameworks.
    for framework in sorted(pods.rglob("*.xcframework/ios-arm64/*.framework")):
        for source in sorted((framework / "Headers").rglob("*")):
            if source.suffix not in (".h", ".hpp") or not source.is_file():
                continue

            dest = common / source.name

            if not dest.exists() and not dest.is_symlink():
                dest.symlink_to(source)

    selected = list({t["name"]: t for app in apps
                     for t in target_dependencies(libraries, app)}.values())

    if any(t["name"] == "ExpoModulesJSI" for t in selected):
        run(["python3", SCRIPTS / "build-jsi.py"], project, job / "build-jsi.log", env)

    for target in selected + apps:
        if any(s["path"].endswith(".swift") for s in target["sources"]):
            run(
                ["python3", SCRIPTS / "compile-swift.py", target["name"]],
                project,
                job / ("swift-" + target["name"] + ".log"),
                env,
            )

    compile_and_link(config, job, selected, apps)


def compile_and_link(config, job, selected, apps):
    project, build = job / "project", job / "build"
    tools = config.toolchain
    pods = project / "ios/Pods"
    products = build / "products"
    env = tool_env(config, project, build)

    sources = [
        t
        for t in selected + apps
        if any(
            Path(s["path"]).suffix in (".c", ".m", ".mm", ".cpp", ".cc", ".cxx", ".S", ".s")
            for s in t["sources"]
        )
    ]

    if sources:
        run(
            ["python3", SCRIPTS / "compile-pods.py", *[t["name"] for t in sources]],
            project,
            job / "compile.log",
            env,
        )

    archives = []

    for target in selected:
        out = products / target["name"]
        objects = list(out.glob("*.o"))

        if objects:
            archive = out / ("lib" + target["name"] + ".a")

            run(
                [config.llvm_ar, "rcs", archive, *objects],
                project,
                job / ("archive-" + target["name"] + ".log"),
            )

            archives.append(archive)

    import shlex

    frameworks = list(pods.rglob("*.xcframework/ios-arm64/*.framework"))
    sdk = config.toolchain / "sdks" / (config.sdk or "iPhoneOS26.5.sdk")
    sdk_version = json.loads((sdk / "SDKSettings.json").read_text())["Version"] if config.sdk else "26.5"
    for app in apps:
        minimum = str(app["settings"].get("IPHONEOS_DEPLOYMENT_TARGET") or "16.4")
        dependencies = target_dependencies(selected, app)
        dependency_names = {t["name"] for t in dependencies}
        needs_cxx = any(t["settings"].get("SWIFT_OBJC_INTEROP_MODE") == "objcxx" for t in dependencies + [app])
        name = app["name"]
        out = products / name
        out.mkdir(exist_ok=True)

        cfg = (
            pods
            / "Target Support Files"
            / ("Pods-" + name)
            / ("Pods-" + name + ".release.xcconfig")
        )

        flags = shlex.split(
            next(
                l.split("=", 1)[1]
                for l in cfg.read_text().splitlines()
                if l.startswith("OTHER_LDFLAGS =")
            )
        )

        flags = [f for f in flags if f != "$(inherited)"]

        if not list(out.glob("*.o")):
            raise ValueError("No compiled objects for target " + name)

        cmd = [
            tools / "darwin-tools/bin/ld64.lld",
            "-arch",
            "arm64",
            "-platform_version",
            "ios",
            minimum,
            sdk_version,
            "--error-limit=0",
            "-syslibroot",
            sdk,
            "-L" + str(sdk / "usr/lib/swift"),
            "-lSystem",
            "-lobjc",
            "-lc++",
            "-dead_strip",
            "-export_dynamic",
            "-rpath",
            "@executable_path/Frameworks",
            "-rpath",
            "@executable_path/../../Frameworks",
            "-o",
            out / name,
            *out.glob("*.o"),
            config.toolchain / "os_version_check.o",
        ]

        cmd += ["-L" + str(a.parent) for a in archives if a.parent.name in dependency_names]
        cmd += ["-F" + str(products / "ExpoModulesJSI")]
        cmd += ["-F" + str(f.parent) for f in frameworks] + flags
        cmd += [tools / "cxx-runtime/compat-markers.o"]

        if needs_cxx:
            cmd += [tools / "cxx-runtime/Cxx.o"]

        if target_kind(app) == "extension":
            cmd += ["-application_extension", "-e", "_NSExtensionMain", "-u", "_main"]

        (out / "link-command.json").write_text(json.dumps(list(map(str, cmd)), indent=2))
        run(cmd, project, job / ("link-" + name + ".log"))


def stage(job):
    build = job / "build"
    libraries, apps = graphs(job)

    main, extensions = target_plan(apps)
    root = build / "stage"
    if root.exists():
        shutil.rmtree(root)
    dest = root / "Payload" / (main["name"] + ".app")
    for app in [main, *extensions]:
        target_dest = dest if app is main else dest / "PlugIns" / (app["name"] + ".appex")
        dependencies = target_dependencies(libraries, app) if any(t.get("name", "").startswith("Pods-") for t in libraries) else libraries
        stage_target(job, app, dependencies, target_dest)
    return dest


def stage_target(job, app, libraries, dest):
    project, build = job / "project", job / "build"
    extension = target_kind(app) == "extension"
    name = app["name"]
    settings = app["settings"]
    dest.mkdir(parents=True)
    info = plistlib.loads((project / "ios" / settings["INFOPLIST_FILE"]).read_bytes())

    variables = {
        **settings,
        "PRODUCT_BUNDLE_PACKAGE_TYPE": "XPC!" if extension else "APPL",
        "PRODUCT_NAME": name,
        "EXECUTABLE_NAME": name,
        "DEVELOPMENT_LANGUAGE": "en",
        "MARKETING_VERSION": settings.get("MARKETING_VERSION") or "1.0",
        "CURRENT_PROJECT_VERSION": settings.get("CURRENT_PROJECT_VERSION") or "1",
    }

    raw = json.dumps(info)
    raw = re.sub(r"\$\(([^)]+)\)", lambda m: str(variables.get(m[1]) or m[0]), raw)

    if "$(" in raw:
        raise ValueError(
            "Unresolved variables in Info.plist: "
            + ", ".join(sorted(set(re.findall(r"\$\(([^)]+)\)", raw))))
        )

    info = json.loads(raw)

    info.update(
        CFBundleExecutable=name,
        CFBundlePackageType="XPC!" if extension else "APPL",
        CFBundleSupportedPlatforms=["iPhoneOS"],
        DTPlatformName="iphoneos",
        UIDeviceFamily=[
            int(family.strip())
            for family in (settings.get("TARGETED_DEVICE_FAMILY") or "1").split(",")
        ],
        MinimumOSVersion="16.4",
    )

    link_command = build / "products" / name / "link-command.json"
    if link_command.exists():
        command = json.loads(link_command.read_text())
        sdk = Path(command[command.index("-syslibroot") + 1])
        sdk_settings = json.loads((sdk / "SDKSettings.json").read_text())
        sdk_system = plistlib.loads(
            (sdk / "System/Library/CoreServices/SystemVersion.plist").read_bytes()
        )
        # Record the SDK actually linked, without inventing an Xcode build identity.
        info.update(
            MinimumOSVersion=command[command.index("-platform_version") + 2],
            DTSDKName=sdk_settings["CanonicalName"],
            DTPlatformVersion=sdk_settings["Version"],
            DTSDKBuild=sdk_system["ProductBuildVersion"],
            DTPlatformBuild=sdk_system["ProductBuildVersion"],
        )

    if not extension:
        info.pop("UILaunchStoryboardName", None)
        info["UILaunchScreen"] = {}

        info.setdefault(
            "UIApplicationSceneManifest",
            {
                "UIApplicationSupportsMultipleScenes": False,
                "UISceneConfigurations": {
                    "UIWindowSceneSessionRoleApplication": [
                        {
                            "UISceneConfigurationName": "Default Configuration",
                            "UISceneDelegateClassName": (settings.get("PRODUCT_MODULE_NAME") or name)
                            + ".SceneDelegate",
                        }
                    ]
                },
            },
        )

    entitlement_path = settings.get("CODE_SIGN_ENTITLEMENTS")
    if entitlement_path:
        entitlements = (project / "ios" / entitlement_path).read_text()
        entitlements = re.sub(r"\$[({]([^)}]+)[)}]", lambda m: str(variables.get(m[1]) or m[0]), entitlements)
        if "$(" in entitlements or "${" in entitlements:
            raise ValueError("Unresolved entitlement variables for " + name)
        (dest / "ios-anywhere-entitlements.plist").write_text(entitlements)

    binary = build / "products" / name / name
    shutil.copy2(binary, dest / name)
    (dest / name).chmod(0o755)

    for target in libraries:
        if not target["resources"] or target.get("name") == "ExpoWidgets":
            continue

        resource = dest / ((target["settings"].get("PRODUCT_NAME") or target["name"]) + ".bundle")
        resource.mkdir(exist_ok=True)

        (resource / "Info.plist").write_bytes(
            plistlib.dumps(
                {
                    "CFBundleIdentifier": "org.cocoapods." + target["name"],
                    "CFBundlePackageType": "BNDL",
                    "CFBundleVersion": "1",
                }
            )
        )

        for filename in target["resources"]:
            src = Path(filename)

            if not src.exists():
                raise ValueError("Native resource not generated: " + filename)

            if src.is_dir():
                shutil.copytree(src, resource / src.name, dirs_exist_ok=True)
            else:
                shutil.copy2(src, resource / src.name)

    for src in (build / "app-resources").iterdir():
        if extension and src.name not in ("EXConstants.bundle", "ExpoWidgets.bundle"):
            continue
        if src.name == "ExpoWidgets.bundle" and not any(t.get("name") == "ExpoWidgets" for t in libraries):
            continue
        if src.is_dir():
            shutil.copytree(src, dest / src.name, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest / src.name)

    for resource in dest.glob("*.bundle"):
        if not (resource / "Info.plist").exists():
            (resource / "Info.plist").write_bytes(
                plistlib.dumps(
                    {
                        "CFBundleIdentifier": "org.expo." + resource.stem,
                        "CFBundlePackageType": "BNDL",
                        "CFBundleVersion": "1",
                    }
                )
            )

    for filename in app.get("resources", []):
        src = Path(filename)
        # Asset catalogs and storyboards use the existing Linux fallbacks below.
        if src.suffix in (".xcassets", ".storyboard"):
            continue
        if not src.exists():
            raise ValueError("Target resource not generated: " + filename)
        if src.is_dir():
            shutil.copytree(src, dest / src.name, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest / src.name)

    for src in (project / "ios" / name).rglob("*"):
        if src.name in (
            "Expo.plist",
            "GoogleService-Info.plist",
            "PrivacyInfo.xcprivacy",
        ):
            shutil.copy2(src, dest / src.name)

    icons = list((project / "ios" / name).glob("Images.xcassets/AppIcon.appiconset/*.png"))

    if icons:
        from PIL import Image

        with Image.open(icons[0]) as icon:
            for filename, size in [
                ("AppIcon60x60@2x.png", 120),
                ("AppIcon60x60@3x.png", 180),
                ("AppIcon76x76@2x~ipad.png", 152),
                ("AppIcon83.5x83.5@2x~ipad.png", 167),
            ]:
                if not (dest / filename).exists():
                    icon.convert("RGB").resize((size, size), Image.Resampling.LANCZOS).save(
                        dest / filename
                    )

        info["CFBundleIcons"] = {"CFBundlePrimaryIcon": {"CFBundleIconFiles": ["AppIcon60x60"]}}

        info["CFBundleIcons~ipad"] = {
            "CFBundlePrimaryIcon": {
                "CFBundleIconFiles": [
                    "AppIcon60x60",
                    "AppIcon76x76",
                    "AppIcon83.5x83.5",
                ]
            }
        }

    # shortcut: Assets.car must already be compiled; Linux asset compilation is not implemented.
    if icons and (dest / "Assets.car").is_file():
        icon_name = settings.get("ASSETCATALOG_COMPILER_APPICON_NAME") or "AppIcon"
        for key in ("CFBundleIcons", "CFBundleIcons~ipad"):
            info[key]["CFBundlePrimaryIcon"]["CFBundleIconName"] = icon_name

    for src in (project / "ios" / name).glob("Images.xcassets/SplashScreenLogo.imageset/*.png"):
        scale = "@3x" if "@3x" in src.stem else "@2x" if "@2x" in src.stem else ""
        shutil.copy2(src, dest / ("SplashScreenLogo" + scale + ".png"))
        info["UILaunchScreen"] = {"UIImageName": "SplashScreenLogo"}

    (dest / "Info.plist").write_bytes(plistlib.dumps(info))

    vendor_frameworks = list((project / "ios/Pods").rglob("*.xcframework/ios-arm64/*.framework"))
    built_jsi = build / "products/ExpoModulesJSI/ExpoModulesJSI.framework"
    if built_jsi.exists():
        vendor_frameworks = [fw for fw in vendor_frameworks if fw.name != built_jsi.name] + [built_jsi]
    aggregate = "Pods-" + name
    link_settings = project / "ios/Pods/Target Support Files" / aggregate / (aggregate + ".release.xcconfig")
    if link_settings.exists():
        import shlex
        flags = shlex.split(next(line.split("=", 1)[1] for line in link_settings.read_text().splitlines()
                                 if line.startswith("OTHER_LDFLAGS =")))
        linked_frameworks = {flags[i + 1] for i, flag in enumerate(flags[:-1])
                             if flag in ("-framework", "-weak_framework")}
        vendor_frameworks = [fw for fw in vendor_frameworks if fw.stem in linked_frameworks]
    for fw in vendor_frameworks:
        data = (fw / fw.stem).read_bytes()

        # MH_DYLIB only; static vendor frameworks are already linked into the executable.
        if data[:4] == bytes.fromhex("cffaedfe") and int.from_bytes(data[12:16], "little") == 6:
            shutil.copytree(
                fw,
                dest / "Frameworks" / fw.name,
                ignore=shutil.ignore_patterns("Headers", "Modules", "_CodeSignature"),
                dirs_exist_ok=True,
            )

    return dest


def build(config, source, output, credentials):
    credentials = credentials or source / "credentials.json"
    signing.check_output(output)
    signing.check_credentials(credentials)

    if not credentials.is_file() or not json.loads(credentials.read_text()).get("ios"):
        raise ValueError(
            "Provide --credentials with iOS credentials; the default file is the project's credentials.json."
        )

    job = prepare(config, source)
    bundle(config, job)
    bundle_widgets(config, job)
    native(config, job)
    package(config, job, output, credentials)


def package(config, job, output, credentials):
    signing.package(config, stage(job), output, credentials, job)
