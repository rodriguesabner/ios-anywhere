"""External Expo builds: per-project sources and products, shared Linux toolchain."""

import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import stat
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
                config.env()["PATH"],
            ]
        ),
    )

    return env


def tools_ruby(config):
    return config.toolchain / "ruby/usr/bin/ruby3.2"


def patch_glog_configure(project):
    path = project / "node_modules/react-native/scripts/ios-configure-glog.sh"
    if not path.is_file():
        return
    text = path.read_text()
    # React Native's no-xcrun fallback produces a literal ':-/usr/bin/gcc'.
    replacements = {
        'export CC="$CC:-$(which gcc)"': 'export CC="clang"',
        'export CXX="$CXX:-$(which g++ || true)"': 'export CXX="clang++"',
        'export CXX="$CXX:-$CC"': 'export CXX="${CXX:-$CC}"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    if text != path.read_text():
        path.write_text(text)


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
    patch_glog_configure(project)

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

    names = ('splashScreenFilename', '"SplashScreen"')
    name = next((name for name in names if f'    if let vc = UIStoryboard(name: {name}, bundle: nil).instantiateInitialViewController() {{' in text), None)

    if name is None:
        raise ValueError("Unrecognized splash screen implementation for the Linux build.")

    marker = f"    if let vc = UIStoryboard(name: {name}, bundle: nil).instantiateInitialViewController() {{"

    # shortcut: no ibtool on Linux; use UIKit launch resources until storyboard compilation is supported.
    text = text.replace(
        marker,
        f'    guard Bundle.main.path(forResource: {name}, ofType: "storyboardc") != nil else {{ return }}\n'
        + marker,
    )

    path.write_text(text)


def unlock_cached_pod(project, name):
    # CocoaPods marks downloaded sources read-only; patches run only in our build copy.
    pod = project / "ios/Pods" / name
    if not pod.exists():
        return
    if pod.is_symlink():
        raise ValueError(f"Refusing to modify a symlinked Pod: {pod}")
    for path in [pod, *pod.rglob("*")]:
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        if not mode & stat.S_IWUSR:
            path.chmod(stat.S_IMODE(mode) | stat.S_IWUSR)


def patch_native_sources(project):
    patch_splash(project)
    fmt = project / "ios/Pods/fmt/include/fmt/base.h"
    if fmt.is_file():
        text = fmt.read_text()
        marker = "#if !defined(__cpp_lib_is_constant_evaluated)"
        # fmt 11.0 ignores an explicit FMT_USE_CONSTEVAL override; newer releases already honor it.
        if marker in text:
            unlock_cached_pod(project, "fmt")
            fmt.write_text(text.replace(marker, "#if defined(FMT_USE_CONSTEVAL)\n// Use the compiler-provided setting.\n#elif !defined(__cpp_lib_is_constant_evaluated)", 1))
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


def prepare_glog(config, project, build, job):
    pods = project / "ios/Pods"
    header = pods / "glog/src/config.h"
    if header.is_file():
        text = header.read_text()
        if any(f"#define {name} 1" not in text for name in ("HAVE_PTHREAD", "HAVE_PREAD")):
            patched = text
            for name in ("HAVE_PTHREAD", "HAVE_PREAD"):
                if f"#define {name} 1" in text:
                    continue
                pattern = rf"(?m)^(?:/\* #undef {name} \*/|#define {name} 0)$"
                patched, count = re.subn(pattern, f"#define {name} 1", patched)
                if count != 1:
                    raise ValueError(f"Unrecognized glog configuration for {name}; refusing to guess.")
            # CocoaPods may prune configure. Link the actual iOS APIs before repairing its cached results.
            probe = build / "glog-ios-probe.c"
            probe.write_text("""#include <pthread.h>
#include <unistd.h>
static void *worker(void *arg) { return arg; }
int main(void) {
    pthread_t thread;
    pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
    char byte;
    int result = pthread_mutex_lock(&mutex);
    result += pthread_create(&thread, 0, worker, 0);
    result += pthread_join(thread, 0);
    result += pthread_mutex_unlock(&mutex);
    return result + (int)pread(0, &byte, 1, 0);
}
""")
            run([SCRIPTS / "bin/clang", probe, "-o", build / "glog-ios-probe"],
                build, job / "glog-probe.log", tool_env(config, project, build))
            unlock_cached_pod(project, "glog")
            header.write_text(patched)
    # glog includes log_severity.h inside namespace google; implicit submodule imports are invalid there.
    for modulemap in (pods / "Target Support Files/glog").glob("*.modulemap"):
        text = modulemap.read_text()
        patched = text.replace("umbrella header", "textual header")
        if "textual header" in patched:
            patched = re.sub(r"module\s+\*\s*\{\s*export\s+\*\s*\}", "", patched)
        if patched != text:
            modulemap.write_text(patched)


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
    prepare_glog(config, project, build, job)
    libraries, apps = graphs(job)

    if len(apps) != 1:
        raise ValueError("External Expo projects: extensions still require resource and signing adaptations.")

    patch_scene(project, apps)

    if any(
        Path(f["path"]).suffix in (".m", ".mm", ".c", ".cpp") for a in apps for f in a["sources"]
    ):
        raise ValueError("The external main target must currently use Swift.")

    rn = project / "node_modules/react-native"
    version = json.loads((rn / "package.json").read_text())["version"]

    for script in [
        "scripts/replace-rncore-version.js",
        "third-party-podspecs/replace_dependencies_version.js",
        "sdks/hermes-engine/utils/replace_hermes_version.js",
    ]:
        if (rn / script).exists():
            run(
                ["node", rn / script, "-c", "Release", "-r", version, "-p", pods],
                pods,
                job / (Path(script).stem + ".log"),
                env,
            )

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

    # Select dependencies from the app's own aggregate target, in dependency order.
    by_name = {t["name"]: t for t in libraries}
    selected = []
    visited = set()

    def visit(name):
        if name in visited:
            return

        visited.add(name)

        if name not in by_name:
            return

        target = by_name[name]

        for dependency in target["dependencies"]:
            visit(dependency)

        selected.append(target)

    for app in apps:
        visit("Pods-" + app["name"])

    if not selected:
        raise ValueError("The graph does not contain the app's CocoaPods aggregate target.")

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
        for t in selected
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
    sdk = config.toolchain / "sdks/iPhoneOS26.5.sdk"
    needs_cxx = any(t["settings"].get("SWIFT_OBJC_INTEROP_MODE") == "objcxx" for t in selected)
    minimum = "16.4"

    for app in apps:
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

        cmd = [
            tools / "darwin-tools/bin/ld64.lld",
            "-arch",
            "arm64",
            "-platform_version",
            "ios",
            minimum,
            "26.5",
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

        cmd += ["-L" + str(a.parent) for a in archives]
        cmd += ["-F" + str(f.parent) for f in frameworks] + flags
        cmd += [tools / "cxx-runtime/compat-markers.o"]

        if needs_cxx:
            cmd += [tools / "cxx-runtime/Cxx.o"]

        if app["settings"].get("APPLICATION_EXTENSION_API_ONLY") == "YES":
            cmd += ["-application_extension", "-e", "_NSExtensionMain", "-u", "_main"]

        (out / "link-command.json").write_text(json.dumps(list(map(str, cmd)), indent=2))
        run(cmd, project, job / ("link-" + name + ".log"))


def stage(job):
    project, build = job / "project", job / "build"
    libraries, apps = graphs(job)

    # shortcut: extension resource scripts need dedicated support before external widget builds.
    if len(apps) != 1:
        raise ValueError(
            "The external backend still requires adaptation for multiple targets/extensions."
        )

    app = apps[0]
    name = app["name"]
    settings = app["settings"]
    root = build / "stage"

    if root.exists():
        shutil.rmtree(root)

    dest = root / "Payload" / (name + ".app")
    dest.mkdir(parents=True)
    info = plistlib.loads((project / "ios" / settings["INFOPLIST_FILE"]).read_bytes())

    variables = {
        **settings,
        "PRODUCT_BUNDLE_PACKAGE_TYPE": "APPL",
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
        CFBundlePackageType="APPL",
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

    binary = build / "products" / name / name
    shutil.copy2(binary, dest / name)
    (dest / name).chmod(0o755)

    for target in libraries:
        if not target["resources"]:
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

    for fw in (project / "ios/Pods").rglob("*.xcframework/ios-arm64/*.framework"):
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
    native(config, job)
    package(config, job, output, credentials)


def package(config, job, output, credentials):
    signing.package(config, stage(job), output, credentials, job)
