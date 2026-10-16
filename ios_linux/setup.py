"""Guided Expo and Godot setup, isolated from existing toolchains and signing credentials."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from .config import Config, default_config

SDK_NAME = "iPhoneOS18.5.sdk"
SDK_REPO = "https://github.com/xybp888/iOS-SDKs.git"
SDK_REVISION = "ad607cb07fe4ad1c9b91cf970bd228c2a9253207"
GODOT_RELEASE = "https://github.com/godotengine/godot-builds/releases/download/4.5.1-stable/"
DOWNLOADS = {
    "linker": (
        "https://github.com/xtool-org/darwin-tools-linux-llvm/releases/download/v1.1.0/toolset-x86_64.tar.gz",
        "a5166f2d56ac45707e5ef2f3c20a41a94af8ef0c0456354224dd08656e874188",
    ),
    "editor": (
        GODOT_RELEASE + "Godot_v4.5.1-stable_linux.x86_64.zip",
        "02ec53d1cc7dbb9cc6355393c61b9ab43d1244751a124f10248a4802830788cd",
    ),
    "templates": (
        GODOT_RELEASE + "Godot_v4.5.1-stable_export_templates.tpz",
        "1998af37f1387684e2c211cdb483daf492fc64dc6b12096bddcdca25b6910c86",
    ),
}
MIN_FREE_BYTES = 8 * 1024**3


def run(command, **kwargs):
    subprocess.run([str(arg) for arg in command], check=True, **kwargs)


def confirm(message, yes):
    if yes:
        return
    if not sys.stdin.isatty():
        raise ValueError("Interactive setup needs a terminal. Use --yes and --sdk-source local|mirror.")
    if input(message + " [y/N] ").strip().lower() not in ("y", "yes"):
        raise ValueError("Setup cancelled; existing installations are unchanged.")


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(name, cache, downloads=None):
    url, digest = (DOWNLOADS if downloads is None else downloads)[name]
    destination = cache / url.rsplit("/", 1)[1]
    if destination.exists():
        if sha256(destination) != digest:
            raise ValueError(f"Checksum mismatch: {destination}. Remove this cached download and retry.")
        print(f"[download] Reusing verified {destination.name}", flush=True)
        return destination
    partial = destination.with_name(destination.name + ".part")
    if partial.exists() and sha256(partial) == digest:
        partial.rename(destination)
        return destination
    print(f"[download] {url}", flush=True)
    run(["curl", "--fail", "--location", "--proto", "=https", "--proto-redir", "=https",
         "--retry", "3", "--connect-timeout", "30", "--continue-at", "-",
         "--output", partial, url])
    if sha256(partial) != digest:
        partial.unlink()
        raise ValueError(f"Checksum mismatch for {destination.name}; rejected download.")
    partial.rename(destination)
    return destination


def extract_member(archive, member, destination):
    # Write only explicitly selected members to fixed destinations, never archive paths.
    destination.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(member) as source, destination.open("wb") as target:
        shutil.copyfileobj(source, target)


def install_tools(tools, cache):
    print("[1/5] Installing compiler and linker", flush=True)
    compiler = tools / "swift/usr/bin/clang"
    compiler.parent.mkdir(parents=True)
    # Godot compiles C/C++ support only; Expo still requires its separate Swift toolchain.
    compiler.symlink_to(shutil.which("clang-18"))
    linker_archive = download("linker", cache)
    unpacked = tools / "linker-unpacked"
    with tarfile.open(linker_archive) as archive:
        archive.extractall(unpacked, filter="data")
    candidates = list(unpacked.rglob("bin/ld64.lld"))
    if len(candidates) != 1:
        raise ValueError("Unexpected linker archive layout.")
    shutil.move(str(candidates[0].parent.parent), tools / "darwin-tools")
    if unpacked.exists():
        shutil.rmtree(unpacked)

    print("[2/5] Installing Godot 4.5.1 and iOS device libraries", flush=True)
    with zipfile.ZipFile(download("editor", cache)) as archive:
        extract_member(archive, "Godot_v4.5.1-stable_linux.x86_64", tools / "godot/godot")
    (tools / "godot/godot").chmod(0o755)
    with zipfile.ZipFile(download("templates", cache)) as archive:
        extract_member(archive, "templates/ios.zip", tools / "ios.zip")
    with zipfile.ZipFile(tools / "ios.zip") as archive:
        for library, suffix in [
            ("libgodot.a", "libgodot.ios.release.xcframework/ios-arm64/libgodot.a"),
            ("libMoltenVK.a", "MoltenVK.xcframework/ios-arm64/libMoltenVK.a"),
        ]:
            matches = [name for name in archive.namelist() if name == suffix or name.endswith("/" + suffix)]
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one release device slice: {suffix}")
            extract_member(archive, matches[0], tools / "godot" / library)
    (tools / "ios.zip").unlink()


def validate_sdk(path, version="18.5"):
    data = json.loads((path / "SDKSettings.json").read_text())
    if str(data.get("Version")) != version:
        raise ValueError(f"Setup requires the iPhoneOS {version} SDK.")
    for name in ["usr/lib/libSystem.tbd", "usr/include/stdio.h", "System/Library/Frameworks"]:
        if not (path / name).exists():
            raise ValueError(f"Incomplete SDK: missing {name}")
    for entry in path.rglob("*"):
        if entry.is_symlink() and not entry.resolve().is_relative_to(path.resolve()):
            raise ValueError(f"SDK contains a link outside its directory: {entry}")


def install_sdk(tools, source, local, version="18.5"):
    name = f"iPhoneOS{version}.sdk"
    print(f"[3/5] Preparing {name}", flush=True)
    destination = tools / "sdks" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source == "local":
        validate_sdk(local, version)
        shutil.copytree(local, destination, symlinks=True)
    else:
        checkout = tools / "sdk-checkout"
        run(["git", "init", "--quiet", checkout])
        run(["git", "-C", checkout, "remote", "add", "origin", SDK_REPO])
        run(["git", "-C", checkout, "config", "remote.origin.promisor", "true"])
        run(["git", "-C", checkout, "config", "remote.origin.partialclonefilter", "blob:none"])
        run(["git", "-C", checkout, "fetch", "--depth=1", "--filter=blob:none", "origin", SDK_REVISION])
        run(["git", "-C", checkout, "sparse-checkout", "set", name])
        run(["git", "-C", checkout, "checkout", "--detach", SDK_REVISION])
        revision = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        if revision != SDK_REVISION:
            raise ValueError("SDK checkout revision mismatch.")
        shutil.move(str(checkout / name), destination)
        shutil.rmtree(checkout)
    validate_sdk(destination, version)


def smoke_test(tools):
    from . import godot
    print("[5/5] Checking tools and linking a native Godot executable", flush=True)
    with tempfile.TemporaryDirectory(prefix="setup-check-", dir=tools) as temp:
        config = Config(tools, Path(temp))
        config.doctor("godot")
        run([tools / "godot/godot", "--headless", "--version"])
        try:
            godot.native(config, Path(temp))
        except ValueError:
            # These compiler-only logs contain no signing inputs; show diagnostics before cleanup.
            for log in sorted(Path(temp).glob("*.log")):
                print(f"--- {log.name} ---", file=sys.stderr)
                print("\n".join(log.read_text(errors="replace").splitlines()[-20:]), file=sys.stderr)
            raise
        with (Path(temp) / "Game").open("rb") as binary:
            if binary.read(4) != b"\xcf\xfa\xed\xfe":
                raise ValueError("Native link did not produce a Mach-O executable.")
        run(["node", "-e", "require(process.argv[1]).ZsignWasmClient.create().then(() => console.log('Signer ready')).catch(e => { console.error(e); process.exit(1); })",
             tools / "signing/node_modules/zsign-wasm"])


def check_space(path, minimum=MIN_FREE_BYTES):
    while not path.exists():
        path = path.parent
    free = shutil.disk_usage(path).free
    if free < minimum:
        raise ValueError(f"Setup needs at least {minimum // 1024**3} GiB free before downloads; available: {free / 1024**3:.1f} GiB. Free space or use --toolchain on another disk.")


def setup(args):
    engine = args.setup_engine or args.engine or "godot"
    expo = None
    if engine == "expo":
        from . import setup_expo as expo
        expo.check_host()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("Guided setup currently supports Linux x86_64 only.")
    if not hasattr(tarfile, "data_filter"):
        raise ValueError("Setup requires Python with safe tar extraction filters (3.11.8+ or 3.12+).")
    print(f"{engine.title()} setup. Existing configurations and credentials are preserved.")
    versions = expo.SDK_VERSIONS if expo else ("18.5",)
    sdk_label = "SDK folder containing iPhoneOS26.4.sdk and iPhoneOS26.5.sdk" if expo else "iPhoneOS18.5.sdk folder"
    config_path = (args.config or default_config()).expanduser().absolute()
    tools = (args.toolchain or Path.home() / ".local/share/ios-anywhere/toolchain").expanduser().absolute()
    for path in (config_path, tools):
        if path.exists() or path.is_symlink():
            raise ValueError(f"Preserving existing path: {path}. Select a new --config and --toolchain, or use doctor for your existing installation.")
    config_path, tools = config_path.resolve(), tools.resolve()
    if config_path.is_relative_to(tools) or tools.is_relative_to(config_path):
        raise ValueError("Keep the config outside the toolchain directory.")
    source = args.sdk_source
    if args.sdk and source not in (None, "local"):
        raise ValueError("--sdk can only be used with --sdk-source local.")
    if args.sdk:
        source = "local"
    if not source:
        if args.yes or not sys.stdin.isatty():
            raise ValueError("Choose --sdk-source local or --sdk-source mirror explicitly.")
        print(f"SDK source:\n  1. Import a local {sdk_label}\n  2. Download from the unofficial xybp888/iOS-SDKs mirror")
        choice = input("Choose [1/2]: ").strip()
        if choice not in ("1", "2"):
            raise ValueError("Choose 1 or 2.")
        source = {"1": "local", "2": "mirror"}[choice]
    local = args.sdk
    if source == "local":
        if local is None:
            if args.yes or not sys.stdin.isatty():
                raise ValueError(f"Supply --sdk pointing to your {sdk_label}.")
            local = Path(input("SDK folder: ").strip())
        local = local.expanduser().resolve()
        for version in versions:
            validate_sdk(local / f"iPhoneOS{version}.sdk" if expo else local, version)
    else:
        print(f"Unofficial SDK source: {SDK_REPO}\nPinned revision: {SDK_REVISION}\nThis mirror is not Apple-authenticated. Apple SDK terms still apply.")
    if expo:
        check_space(tools.parent, 20 * 1024**3)
    else:
        check_space(tools.parent)
    print(f"Toolchain: {tools}\nConfiguration: {config_path}\nDownloads are cached beside the toolchain and verified against pinned SHA-256 hashes.")
    confirm(f"Install {engine.title()} tools and the selected SDKs?", args.yes)
    packages = {"clang-18": "clang-18", "curl": "curl", "git": "git", "node": "nodejs", "npm": "npm", "openssl": "openssl", "ideviceinstaller": "ideviceinstaller", "idevicepair": "libimobiledevice-utils", "usbmuxd": "usbmuxd"}
    missing = [package for command, package in packages.items() if not shutil.which(command)]
    if expo:
        # apt checks package installation too: shared libraries have no executable to probe.
        missing = expo.PACKAGES
    if missing:
        if not shutil.which("apt-get"):
            raise ValueError("Install these system packages first: " + " ".join(missing))
        print("Required system packages: " + " ".join(missing))
        confirm("Install missing packages with apt-get (may require sudo)?", args.yes)
        prefix = [] if os.geteuid() == 0 else ["sudo"]
        run([*prefix, "apt-get", "update"])
        run([*prefix, "apt-get", "install", "-y", *missing, "ca-certificates"])
    tools.parent.mkdir(parents=True, exist_ok=True)
    # Serialize downloads and publishing for this destination, including parallel invocations.
    with (tools.parent / ("." + tools.name + ".setup.lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another setup is using this toolchain destination.") from None
        if tools.exists() or tools.is_symlink() or config_path.exists() or config_path.is_symlink():
            raise ValueError("Destination appeared during setup; preserving it.")
        cache = tools.parent / ("." + tools.name + "-downloads")
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="." + tools.name + "-setup-", dir=tools.parent) as temp:
            staged = Path(temp) / "toolchain"
            staged.mkdir()
            if expo:
                expo.install_tools(staged, cache)
                for version in versions:
                    install_sdk(staged, source, local / f"iPhoneOS{version}.sdk" if local else None, version)
                if source == "mirror":
                    expo.patch_mirror_sdk(staged)
                expo.prepare_runtime(staged)
            else:
                install_tools(staged, cache)
                install_sdk(staged, source, local)
            print("[4/5] Installing zsign-wasm 0.0.4", flush=True)
            run(["npm", "install", "--prefix", staged / "signing", "--save-exact", "--ignore-scripts", "--no-audit", "--no-fund", "zsign-wasm@0.0.4"], env=Config(staged, staged / "check-cache").env())
            if expo:
                expo.smoke_test(staged)
            else:
                smoke_test(staged)
            (staged / "setup-manifest.json").write_text(json.dumps({
                "engine": engine, "versions": {"swift": "6.4", "node": "22.20.0", "expo_macros": "0.6.1", "cocoapods": "1.17.0"} if expo else {"godot": "4.5.1", "clang": "system clang-18"},
                "sdks": versions,
                "cxx_revision": expo.CXX_REVISION if expo else None,
                "sdk_source": source, "sdk_revision": SDK_REVISION if source == "mirror" else None,
                "downloads": {"linker": DOWNLOADS["linker"], **expo.DOWNLOADS} if expo else DOWNLOADS,
            }, indent=2) + "\n")
            # Publish only a toolchain that passes the native link check.
            if tools.exists() or tools.is_symlink():
                raise ValueError("Toolchain destination appeared during setup; preserving it.")
            staged.rename(tools)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("x") as config_file:
            json.dump({"toolchain": str(tools), "cache": str(tools.parent / "build-cache"), "llvm_ar": "llvm-ar-18" if expo else "llvm-ar"}, config_file, indent=2)
            config_file.write("\n")
    print(f"Setup complete. Config: {config_path}\nNative link passed; no IPA was signed or installed.\nNext: ios-anywhere --config {config_path} --engine {engine} doctor\nVerified downloads kept in {cache}; remove that directory to reclaim space when no setup is running.")
