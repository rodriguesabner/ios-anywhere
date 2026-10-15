"""Rebuild small runtime objects; optionally build the Swift 6.2 Cxx overlay."""

import argparse
from pathlib import Path
import shlex
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--toolchain", type=Path, required=True)
parser.add_argument(
    "--cxx-sources", type=Path, help="Swift swift-6.2-RELEASE/stdlib/public/Cxx"
)
args = parser.parse_args()
tools = args.toolchain.resolve()
source = Path(__file__).parent
runtime = tools / "cxx-runtime"
runtime.mkdir(exist_ok=True)
clang = tools / "swift/usr/bin/clang"
subprocess.run(
    [
        str(clang),
        "-target",
        "arm64-apple-ios16.4",
        "-isysroot",
        str(tools / "sdks/iPhoneOS26.4.sdk"),
        "-include",
        "stdbool.h",
        "-O2",
        "-c",
        str(source / "os_version_check.c"),
        "-o",
        str(tools / "os_version_check.o"),
    ],
    check=True,
)
subprocess.run(
    [
        str(clang),
        "-target",
        "arm64-apple-ios16.4",
        "-c",
        str(source / "compat-markers.c"),
        "-o",
        str(runtime / "compat-markers.o"),
    ],
    check=True,
)
if args.cxx_sources:
    interface = (
        tools
        / "darwin-resource/iphoneos/Cxx.swiftmodule/arm64-apple-ios.swiftinterface"
    )
    flags = shlex.split(
        next(
            line.split(": ", 1)[1]
            for line in interface.read_text().splitlines()
            if line.startswith("// swift-module-flags:")
        )
    )
    flags = [
        flag.replace("arm64-apple-ios16.4", "arm64-apple-ios27.0") for flag in flags
    ]
    sources = sorted(args.cxx_sources.resolve().glob("*.swift"))
    if not sources or any("protocol CxxIterable" in p.read_text() for p in sources):
        raise ValueError("Use os fontes Cxx de swift-6.2-RELEASE.")
    command = [
        str(tools / "swift/usr/bin/swiftc"),
        "-frontend",
        "-emit-object",
        *flags,
        "-sdk",
        str(tools / "sdks/iPhoneOS27.0.sdk"),
        "-resource-dir",
        str(tools / "darwin-resource"),
        "-I",
        str(tools / "darwin-resource/shims"),
        "-module-cache-path",
        str(runtime / "module-cache"),
        "-disable-implicit-concurrency-module-import",
        "-disable-implicit-string-processing-module-import",
        "-parse-as-library",
        "-whole-module-optimization",
        "-o",
        str(runtime / "Cxx.o"),
        "-emit-module-path",
        str(runtime / "Cxx.swiftmodule"),
        "-emit-module-interface-path",
        str(runtime / "Cxx.swiftinterface"),
        "-cxx-interoperability-mode=default",
        "-Xcc",
        "-nostdinc++",
        # shortcut: upstream availability aliases are absent; this overlay is restricted to iOS 27.
        "-disable-availability-checking",
        *map(str, sources),
    ]
    subprocess.run(command, check=True)
    if "CxxIterable" in (runtime / "Cxx.swiftinterface").read_text():
        raise ValueError("Overlay incompatível.")
    modules = runtime / "modules/Cxx.swiftmodule"
    modules.mkdir(parents=True, exist_ok=True)
    for suffix in ["swiftinterface", "swiftmodule"]:
        shutil.copy2(
            runtime / ("Cxx." + suffix), modules / ("arm64-apple-ios." + suffix)
        )
