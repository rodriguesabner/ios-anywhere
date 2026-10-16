"""Ubuntu 24.04 Expo toolchain recipe; no application or credentials required."""

from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

from . import setup as common
from .config import Config, SCRIPTS

SDK_VERSIONS = ("26.4", "26.5")
CXX_REVISION = "1ff1cc1170617ab23ab74aa8b741c8daca1903f6"
UIKIT_STUB_HASH = "a44b79d7e2a6c121e7cc213c3357e89fc42db1a633d9a69db9beb98c4fef33e2"
DOWNLOADS = {
    "swift": (
        "https://download.swift.org/swift-6.4.0-release/ubuntu2404/swift-6.4.0-RELEASE/swift-6.4.0-RELEASE-ubuntu24.04.tar.gz",
        "69f7b2b4dbce6090b6c92194b71149a057e16269093b5a9dded38afc4a05094e",
    ),
    "node": (
        "https://nodejs.org/dist/v22.20.0/node-v22.20.0-linux-x64.tar.xz",
        "00bbd05e306ea68b6e13e17360d0e2f680b493ef95f2fea1c4296ff7437530bc",
    ),
    "apple-macros": (
        "https://github.com/xtool-org/OpenAppleMacros/releases/download/v1.3.0/OpenAppleMacrosServer-x86_64",
        "bc804ac517a4f1df270bacb655c9f7f57635bb4484dd536740b2516ae7a7b441",
    ),
    "compiler-plugin": (
        "https://raw.githubusercontent.com/swiftlang/swift-syntax/050f1a346fbbac0ca2cfb15a95274f7bd1cf0ccf/Sources/SwiftCompilerPlugin/CompilerPlugin.swift",
        "428b8916d36242ae931593b9b194ba4f428c00484150e9d1ef9243072da2c634",
    ),
}
PACKAGES = [
    "curl", "git", "openssl", "ca-certificates", "build-essential", "pkg-config",
    "libicu74", "libcurl4t64", "libxml2", "libsqlite3-0", "libncurses6", "libzstd1",
    "libssl-dev", "zlib1g-dev", "libyaml-dev", "libffi-dev",
    "ruby3.2", "ruby3.2-dev", "ruby-rubygems", "llvm-18",
    "ideviceinstaller", "libimobiledevice-utils", "usbmuxd",
]


def check_host():
    release = platform.freedesktop_os_release()
    if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != "24.04":
        raise ValueError("Expo guided setup currently requires Ubuntu 24.04 x86_64. Existing manually prepared toolchains remain supported.")


def extract_root(archive_path, destination, marker, *, trim_swift=False):
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        unpacked = Path(temp)
        with tarfile.open(archive_path) as archive:
            def members():
                for member in archive:
                    if trim_swift and any(part in member.name for part in (
                        "/usr/lib/swift_static/", "/usr/share/", "/usr/lib/liblldb", "/usr/bin/lldb",
                    )):
                        continue
                    yield member
            archive.extractall(unpacked, members=members(), filter="data")
        matches = list(unpacked.glob("*/" + marker))
        if len(matches) != 1:
            raise ValueError(f"Unexpected archive layout for {archive_path.name}")
        root = matches[0]
        for _ in Path(marker).parts:
            root = root.parent
        shutil.move(root, destination)


def install_tools(tools, cache):
    print("[1/5] Installing Swift 6.4, Node 22, linker, Ruby and CocoaPods", flush=True)
    extract_root(common.download("swift", cache, DOWNLOADS), tools / "swift", "usr/bin/swiftc", trim_swift=True)
    extract_root(common.download("node", cache, DOWNLOADS), tools / "node", "bin/node")
    # The linker archive has bin/ at its root, unlike Swift and Node archives.
    with tarfile.open(common.download("linker", cache)) as archive:
        archive.extractall(tools / "darwin-tools", filter="data")
    if not (tools / "darwin-tools/bin/ld64.lld").is_file():
        raise ValueError("Unexpected linker archive layout")
    (tools / "ruby").mkdir()
    (tools / "ruby/usr").symlink_to("/usr", target_is_directory=True)
    from .expo import tool_env
    env = tool_env(Config(tools, tools / "check-cache"), tools, tools)
    common.run(["/usr/bin/ruby3.2", "/usr/bin/gem", "install", "cocoapods", "-v", "1.17.0", "--no-document", "--env-shebang"], env=env)
    print("[2/5] Installing Apple macros and compiling the Expo host plugin", flush=True)
    macros = tools / "apple-macros"
    (macros / "plugins").mkdir(parents=True)
    shutil.copy2(common.download("apple-macros", cache, DOWNLOADS), macros / "OpenAppleMacrosServer")
    (macros / "OpenAppleMacrosServer").chmod(0o755)
    for name in ("FoundationModelsMacros", "PreviewsMacros", "SwiftUIMacros"):
        (macros / "plugins" / f"lib{name}.so").touch()
    host = tools / "host-macros"
    host.mkdir()
    shutil.copy2(common.download("compiler-plugin", cache, DOWNLOADS), host / "CompilerPlugin.swift")
    common.run(["npm", "install", "--prefix", host, "--save-exact", "--ignore-scripts",
                "--no-audit", "--no-fund", "@expo/expo-modules-macros-plugin@0.6.1"], env=env)
    build_macros(tools)


def build_macros(tools):
    compiler = tools / "swift/usr/bin/swiftc"
    host = tools / "host-macros"
    libraries = tools / "swift/usr/lib/swift/host"
    common.run([compiler, "-parse-as-library", "-emit-module", "-emit-object", "-module-name", "SwiftCompilerPlugin",
                "-I", libraries, "-emit-module-path", host / "SwiftCompilerPlugin.swiftmodule",
                "-o", host / "SwiftCompilerPlugin.o", host / "CompilerPlugin.swift"])
    sources = sorted((host / "node_modules/@expo/expo-modules-macros-plugin/apple/Sources/ExpoModulesMacros").glob("*.swift"))
    if not sources:
        raise ValueError("Expo macro package contains no Swift sources")
    common.run([compiler, "-parse-as-library", "-module-name", "ExpoModulesMacros", "-I", libraries, "-I", host,
                "-L", libraries, "-Xlinker", "-rpath", "-Xlinker", "$ORIGIN/../swift/usr/lib/swift/host",
                *sources, host / "SwiftCompilerPlugin.o", "-o", host / "ExpoModulesMacros-tool"])


def prepare_overlays(tools):
    resource = tools / "darwin-resource"
    resource.mkdir()
    (resource / "clang").symlink_to("../swift/usr/lib/clang/21")
    (resource / "shims").symlink_to("../swift/usr/lib/swift/shims")
    ios = resource / "iphoneos"
    ios.mkdir()
    linux = tools / "swift/usr/lib/swift/linux"
    for module in ("Cxx", "CxxStdlib"):
        source = linux / f"{module}.swiftmodule/x86_64-unknown-linux-gnu.swiftinterface"
        text = source.read_text().replace("x86_64-unknown-linux-gnu", "arm64-apple-ios16.4").replace("-disable-objc-interop", "-enable-objc-interop")
        directory = ios / f"{module}.swiftmodule"
        directory.mkdir()
        (directory / "arm64-apple-ios.swiftinterface").write_text(text)
    for name in ("libcxxshim.h", "libcxxshim.modulemap", "libcxxstdlibshim.h"):
        shutil.copy2(linux / name, ios / name)


def patch_mirror_sdk(tools):
    stub = tools / "sdks/iPhoneOS26.5.sdk/System/Library/PrivateFrameworks/UIKitCore.framework/UIKitCore.tbd"
    if not stub.exists() or common.sha256(stub) != UIKIT_STUB_HASH:
        raise ValueError("SDK mirror UIKitCore stub differs from the validated revision; refusing to patch it")
    stub.rename(stub.with_suffix(".tbd.mirror-backup"))


def prepare_runtime(tools):
    prepare_overlays(tools)
    source = tools / "cxx-source-checkout"
    common.run(["git", "init", "--quiet", source])
    common.run(["git", "-C", source, "remote", "add", "origin", "https://github.com/swiftlang/swift.git"])
    common.run(["git", "-C", source, "config", "remote.origin.promisor", "true"])
    common.run(["git", "-C", source, "config", "remote.origin.partialclonefilter", "blob:none"])
    common.run(["git", "-C", source, "fetch", "--depth=1", "--filter=blob:none", "origin", CXX_REVISION])
    common.run(["git", "-C", source, "sparse-checkout", "set", "stdlib/public/Cxx"])
    common.run(["git", "-C", source, "checkout", "--detach", CXX_REVISION])
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != CXX_REVISION:
        raise ValueError("Swift Cxx source revision mismatch")
    common.run([sys.executable, SCRIPTS / "prepare-runtime.py", "--toolchain", tools,
                "--cxx-sources", source / "stdlib/public/Cxx"])
    shutil.rmtree(source)


def smoke_test(tools):
    print("[5/5] Checking CocoaPods, Swift compilation, native linking and signing tools", flush=True)
    from .expo import tool_env
    with tempfile.TemporaryDirectory(prefix="expo-check-", dir=tools) as temp:
        work = Path(temp)
        config = Config(tools, work, llvm_ar="llvm-ar-18")
        config.doctor("expo")
        env = tool_env(config, work, work)
        common.run([tools / "ruby/usr/bin/ruby3.2", tools / "gems/bin/pod", "--version"], env=env)
        probe = work / "Probe.swift"
        probe.write_text('import UIKit\n@_cdecl("main") public func entry() -> Int32 { return Int32(UIView().tag) }\n')
        common.run([tools / "swift/usr/bin/swiftc", "-target", "arm64-apple-ios16.4",
                    "-sdk", tools / "sdks/iPhoneOS26.4.sdk", "-resource-dir", tools / "darwin-resource",
                    "-I", tools / "darwin-resource/shims", "-module-cache-path", work / "modules",
                    "-parse-as-library", "-emit-object", probe, "-o", work / "Probe.o"])
        sdk = tools / "sdks/iPhoneOS26.5.sdk"
        common.run([tools / "darwin-tools/bin/ld64.lld", "-arch", "arm64", "-platform_version", "ios", "16.4", "26.5",
                    "-syslibroot", sdk, "-L", sdk / "usr/lib", "-L", sdk / "usr/lib/swift",
                    "-F", sdk / "System/Library/Frameworks", "-lSystem", "-lswiftCore", "-lobjc",
                    "-framework", "UIKit", "-framework", "Foundation", "-e", "_main",
                    work / "Probe.o", tools / "os_version_check.o", "-o", work / "Probe"])
        if (work / "Probe").read_bytes()[:4] != b"\xcf\xfa\xed\xfe":
            raise ValueError("Expo smoke test did not produce a Mach-O executable")
        common.run(["node", "-e", "require(process.argv[1]).ZsignWasmClient.create().catch(e=>{console.error(e);process.exit(1)})",
                    tools / "signing/node_modules/zsign-wasm"], env=env)
