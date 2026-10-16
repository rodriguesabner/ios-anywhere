from pathlib import Path
import os
import glob
import json, shlex, subprocess, concurrent.futures, hashlib, sys

toolroot = Path(os.environ["IOS_LINUX_TOOLCHAIN"])
work = toolroot.parent
root = Path(os.environ["IOS_LINUX_BUILD"])
project = Path(os.environ["IOS_LINUX_PROJECT"])
pods = project / "ios/Pods"
sdk = toolroot / "sdks/iPhoneOS26.4.sdk"
graph = json.loads((root / "pods-graph.json").read_text())
products = root / "products"
framework_dirs = list(pods.rglob("*.xcframework/ios-arm64/*.framework"))

for t in graph:
    h = root / "headers" / t["name"]
    h.mkdir(parents=True, exist_ok=True)

    for entry in t["headers"]:
        src = Path(entry["path"])
        dst = h / src.name

        if not dst.exists() and not dst.is_symlink():
            dst.symlink_to(src)

for header in products.glob("*/*-Swift.h"):
    dest = root / "headers/common" / header.name

    if not dest.exists():
        dest.symlink_to(header)


def args(value):
    if isinstance(value, list):
        return [a for v in value for a in shlex.split(str(v))]

    return [x for x in shlex.split(value or "") if x != "$(inherited)"]


def command(t, source):
    s = t["settings"]
    path = Path(source["path"])
    cpp = path.suffix in (".cpp", ".cc", ".cxx", ".mm")
    objc = path.suffix in (".m", ".mm")
    out = products / t["name"]
    out.mkdir(parents=True, exist_ok=True)
    obj = out / (path.stem + "-" + hashlib.sha256(str(path).encode()).hexdigest()[:10] + ".o")

    cmd = [
        str(toolroot / "swift/usr/bin/clang++" if cpp else toolroot / "swift/usr/bin/clang"),
        "-target",
        "arm64-apple-ios16.4",
        "-isysroot",
        str(sdk),
        "-c",
        str(path),
        "-o",
        str(obj),
        "-O1",
        "-DNDEBUG",
        "-fblocks",
        "-fmodules",
        "-fno-cxx-modules",
        "-fmodules-cache-path=" + str(root / "clang-cache"),
        "-Wno-error",
    ]

    if cpp:
        cmd += [
            "-std=" + str(s.get("CLANG_CXX_LANGUAGE_STANDARD") or "c++20"),
            "-stdlib=libc++",
            # shortcut: upstream Clang rejects fmt consteval with this SDK; retain runtime formatting.
            "-DFMT_USE_CONSTEVAL=0",
        ]

    if objc and s.get("CLANG_ENABLE_OBJC_ARC") == "YES":
        cmd += ["-fobjc-arc"]

    for d in args(s.get("GCC_PREPROCESSOR_DEFINITIONS")):
        cmd += ["-D" + d]

    for key, flag in [("HEADER_SEARCH_PATHS", "-I"), ("FRAMEWORK_SEARCH_PATHS", "-F")]:
        for p in args(s.get(key)):
            # Match Clang's working directory even when this script runs from the project.
            pattern = str(pods / p) if not Path(p).is_absolute() else p
            paths = sorted(x for x in glob.glob(pattern, recursive=True) if Path(x).is_dir()) if "**" in p else [p]
            for expanded in dict.fromkeys(paths):
                cmd += [flag, expanded]

    cmd += [
        "-I",
        str(out),
        "-I",
        str(root / "headers/common"),
        "-I",
        str(products),
        "-F",
        str(products / "ExpoModulesJSI"),
        "-I",
        str(root / "headers" / t["name"]),
        "-I",
        str(project / "node_modules/react-native/React"),
    ]

    cmd += [
        "-I",
        str(s.get("PODS_TARGET_SRCROOT") or pods),
        "-I",
        str(project / "node_modules/expo-modules-jsi/apple/Sources/ExpoModulesJSI-Cxx/include"),
    ]

    for fw in framework_dirs:
        cmd += ["-F", str(fw.parent), "-I", str(fw / "Headers")]

    cmd += args(s.get("OTHER_CFLAGS"))

    if cpp:
        cmd += args(s.get("OTHER_CPLUSPLUSFLAGS"))

    pch = s.get("GCC_PREFIX_HEADER")

    if pch and path.suffix not in (".S", ".s"):
        cmd += ["-include", str(pods / pch)]

    cmd += args((source.get("flags") or {}).get("COMPILER_FLAGS"))
    cmd += ["-Wno-error"]

    cmd = [
        x
        for x in cmd
        if x != "$(inherited)"
        and not (x.startswith("-std=") and not cpp)
        and not (x.startswith("-fmodule-map-file=") and not Path(x.split("=", 1)[1]).exists())
    ]

    return cmd, obj


def build(item):
    t, src = item
    cmd, obj = command(t, src)
    digest = hashlib.sha256(json.dumps(cmd).encode()).hexdigest()
    stamp = obj.with_suffix(".cmdhash")
    log = obj.with_suffix(".log")

    if (
        obj.exists()
        and stamp.exists()
        and stamp.read_text() == digest
        and obj.stat().st_mtime > Path(src["path"]).stat().st_mtime
    ):
        return {"target": t["name"], "source": src["path"], "ok": True, "cached": True}

    obj.with_suffix(".command.json").write_text(json.dumps(cmd, indent=2))

    with log.open("w") as f:
        result = subprocess.run(cmd, cwd=pods, stdout=f, stderr=subprocess.STDOUT)

    if result.returncode == 0:
        stamp.write_text(digest)

    return {
        "target": t["name"],
        "source": src["path"],
        "ok": result.returncode == 0,
        "log": str(log),
    }


if __name__ == "__main__":
    selected = set(sys.argv[1:])

    jobs = [
        (t, s)
        for t in graph
        if not selected or t["name"] in selected
        for s in t["sources"]
        if Path(s["path"]).suffix in (".m", ".mm", ".c", ".cc", ".cpp", ".cxx", ".S", ".s")
    ]

    assert jobs, "No native sources selected"
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for index, r in enumerate(pool.map(build, jobs), 1):
            results.append(r)

            if index % 100 == 0:
                print(f"Native {index}/{len(jobs)}", flush=True)

            if not r["ok"]:
                print("FAIL", r["target"], Path(r["source"]).name, flush=True)

    (root / "compile-results.json").write_text(json.dumps(results, indent=2))
    print("Compiled", sum(r["ok"] for r in results), "/", len(results), flush=True)
    sys.exit(0 if all(r["ok"] for r in results) else 1)
