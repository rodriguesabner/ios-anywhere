from pathlib import Path
import os
import json, subprocess, sys, shlex, re

toolroot = Path(os.environ["IOS_LINUX_TOOLCHAIN"])
work = toolroot.parent
root = Path(os.environ["IOS_LINUX_BUILD"])
project = Path(os.environ["IOS_LINUX_PROJECT"])
pods = project / "ios/Pods"
products = root / "products"
apps = json.loads((root / "app-graph.json").read_text())
graph = json.loads((root / "pods-graph.json").read_text()) + apps


def args(v):
    return [
        s
        for x in (v if isinstance(v, list) else [v or ""])
        for s in shlex.split(str(x))
        if s != "$(inherited)"
    ]


for name in sys.argv[1:]:
    t = next(t for t in graph if t["name"] == name)
    s = t["settings"]
    module = s["PRODUCT_MODULE_NAME"] or name
    source_root = pods.parent if name in {a["name"] for a in apps} else pods
    sources = [f["path"] for f in t["sources"] if f["path"].endswith(".swift")]
    assert sources
    products.mkdir(parents=True, exist_ok=True)
    out = products / name
    out.mkdir(exist_ok=True, parents=True)
    # Keep Release assertion semantics while retaining unoptimized code for diagnosis.
    cmd = [
        str(toolroot / "swift/usr/bin/swiftc"),
        "-target",
        (
            "arm64-apple-ios27.0"
            if s.get("SWIFT_OBJC_INTEROP_MODE") == "objcxx"
            else "arm64-apple-ios16.4"
        ),
        "-sdk",
        str(toolroot / "sdks/iPhoneOS27.0.sdk"),
        "-resource-dir",
        str(toolroot / "darwin-resource"),
        "-I",
        str(toolroot / "darwin-resource/shims"),
        "-module-cache-path",
        str(root / "module-cache"),
        "-swift-version",
        (s.get("SWIFT_VERSION") or "5").split(".")[0],
        "-parse-as-library",
        "-whole-module-optimization",
        "-Onone",
        "-assert-config",
        "Release",
        "-module-name",
        module,
        "-emit-module",
        "-emit-module-path",
        str(out / (module + ".swiftmodule")),
        "-emit-objc-header",
        "-emit-objc-header-path",
        str(out / (module + "-Swift.h")),
        "-emit-object",
        "-o",
        str(out / (module + ".o")),
    ]
    for d in products.iterdir():
        if d.is_dir():
            cmd += ["-I", str(d), "-F", str(d)]
    cmd += [
        "-Xcc",
        "-I" + str(toolroot / "swift/usr/include"),
        "-Xcc",
        "-I" + str(root / "headers/common"),
    ]
    for p in args(s.get("HEADER_SEARCH_PATHS")):
        cmd += ["-Xcc", "-I" + p]
    for p in args(s.get("FRAMEWORK_SEARCH_PATHS")):
        cmd += ["-F", p]
    for fw in pods.rglob("*.xcframework/ios-arm64/*.framework"):
        cmd += ["-F", str(fw.parent), "-Xcc", "-I" + str(fw / "Headers")]
    if s.get("SWIFT_OBJC_INTEROP_MODE") == "objcxx":
        cmd += [
            "-I",
            str(toolroot / "cxx-runtime/modules"),
            "-cxx-interoperability-mode=default",
            "-Xcc",
            "-std=" + str(s.get("CLANG_CXX_LANGUAGE_STANDARD") or "c++20"),
        ]
    for condition in args(s.get("SWIFT_ACTIVE_COMPILATION_CONDITIONS")):
        cmd += ["-D", condition]
    flags = args(s.get("OTHER_SWIFT_FLAGS"))
    cmd += flags
    cmd += [
        "-external-plugin-path",
        str(toolroot / "apple-macros/plugins")
        + "#"
        + str(toolroot / "apple-macros/OpenAppleMacrosServer"),
    ]
    if s.get("SWIFT_OBJC_BRIDGING_HEADER"):
        cmd += [
            "-import-objc-header",
            str(source_root / s["SWIFT_OBJC_BRIDGING_HEADER"]),
        ]
    values = {
        **s,
        "SRCROOT": str(source_root),
        "PODS_ROOT": str(pods),
        "PODS_CONFIGURATION_BUILD_DIR": str(products),
    }
    for _ in range(5):
        cmd = [
            re.sub(
                r"\$[({]([A-Za-z_][A-Za-z_0-9]*)[)}]",
                lambda m: str(values.get(m[1]) or m[0]),
                x,
            )
            for x in cmd
        ]
    mac_tool = str(
        project
        / "node_modules/@expo/expo-modules-macros-plugin/apple/ExpoModulesMacros-tool"
    )
    cmd = [
        x.replace(mac_tool, str(toolroot / "host-macros/ExpoModulesMacros-tool"))
        for x in cmd
    ]
    if s.get("APPLICATION_EXTENSION_API_ONLY") == "YES":
        cmd += ["-application-extension"]
    cmd += sources
    (out / "swift-command.json").write_text(json.dumps(cmd, indent=2))
    with (out / "swift-compile.log").open("w") as log:
        r = subprocess.run(cmd, cwd=pods, stdout=log, stderr=subprocess.STDOUT)
    print(name, "Swift exit", r.returncode, flush=True)
    if r.returncode:
        sys.exit(r.returncode)
    support = pods / "Target Support Files" / name / (name + ".modulemap")
    if support.exists():
        text = (
            support.read_text()
            + f'\nmodule {module}.Swift {{ header "{out / (module + "-Swift.h")}" requires objc }}\n'
        )
        for dest in {
            out / (module + ".modulemap"),
            products / module / (module + ".modulemap"),
        }:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_symlink():
                dest.unlink()
            dest.write_text(text)
