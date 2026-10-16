# Installation details

[Back to quick start](../README.md#installation)

### 1. Install the CLI and base tools

The CLI requires **Python 3.11+**. Builds also use Node/npm and OpenSSL; `pip install .` installs Pillow automatically.

For example, on Ubuntu 24.04 x86_64, install the base packages:

```sh
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip openssl curl unzip
python3 --version
```

Install Node.js with npm using the [official Linux installation options](https://nodejs.org/en/download), choosing a version supported by your Expo project. Confirm both are on PATH:

```sh
node --version
npm --version
```

Install this CLI from the repository:

```sh
git clone https://github.com/rodriguesabner/ios-anywhere.git
cd ios-anywhere
python3 -m venv .venv
.venv/bin/pip install .
. .venv/bin/activate
ios-anywhere --version
```

The commands below assume this repository is the current directory and the virtual environment is active. **This installs the CLI, its Python dependency, wrappers, and templates. It does not install an iOS toolchain or Apple credentials.**

### 2. Prepare the external toolchain

For a new **Godot** installation, run `ios-anywhere setup`. For **Expo on Ubuntu 24.04**, the experimental `ios-anywhere setup --engine expo` prepares the tools. See [guided setup](setup.md) before creating a config. It can import a local SDK or download an explicitly selected unofficial mirror. Existing installations are preserved. Other hosts and manually prepared installations use the instructions below.

Use an existing compatible toolchain if you already have one. Otherwise, prepare the components below once, outside the repository and your app:

```sh
export TOOLCHAIN="$HOME/.local/share/ios-anywhere/toolchain"
mkdir -p "$TOOLCHAIN"
```

The paths are part of the current CLI contract; merely installing tools on PATH does not satisfy every check. Follow the complete [expected layout and tested versions](toolchain.md#expected-layout).

**Common compilation and signing tools**

- Obtain a compatible Linux Swift/Clang toolchain from [Swift's official distribution](https://www.swift.org/install/linux/) and place its contents under `$TOOLCHAIN/swift`, with `usr/bin/clang` and `usr/bin/swiftc`. The recorded build environment used Swift 6.4; a generic Linux Swift installation alone does **not** provide all Apple cross-compilation resources.
- Download `toolset-x86_64.tar.gz` from the upstream [darwin-tools-linux-llvm v1.1.0 release](https://github.com/xtool-org/darwin-tools-linux-llvm/releases/tag/v1.1.0). Extract and arrange it so the linker is `$TOOLCHAIN/darwin-tools/bin/ld64.lld`; inspect the archive layout before extracting into an existing toolchain.
- Supply Apple SDKs that you are authorized to obtain and use, starting from [Apple's Xcode resources](https://developer.apple.com/xcode/resources/). The current backend expects `sdks/iPhoneOS18.5.sdk` for Godot and `sdks/iPhoneOS26.4.sdk` plus `sdks/iPhoneOS26.5.sdk` for Expo. The package does not download or license them. SDK versions and stubs are not interchangeable; see the [compatibility notes](toolchain.md#components-in-the-validated-environment).
- Install the external signer using npm:

```sh
npm install --prefix "$TOOLCHAIN/signing" --save-exact zsign-wasm@0.0.4
```

Keep your certificate, password, and provisioning profile outside the repository and toolchain; supply them later through [the credentials file](../credentials.example.json). Installing the signer does not create Apple credentials.

**Expo-specific preparation**

1. Install LLVM's archive tool. For Ubuntu 24.04, `sudo apt-get install llvm-18` supplies `llvm-ar-18`; set `"llvm_ar": "llvm-ar-18"` in your config if there is no unversioned `llvm-ar`.
2. Prepare Ruby 3.2 and its standard libraries using [Ruby's installation guidance](https://www.ruby-lang.org/en/documentation/installation/), arranged under `$TOOLCHAIN/ruby/usr` as described in the toolchain layout. The backend currently uses `ruby/usr/bin/ruby3.2` and explicit Ruby library paths; a different system Ruby is not an automatic substitute.
3. With that matching Ruby and RubyGems environment active, install CocoaPods into the external gems directory:

```sh
GEM_HOME="$TOOLCHAIN/gems" GEM_PATH="$TOOLCHAIN/gems" \
  gem install cocoapods -v 1.17.0 --no-document --env-shebang
```

This uses [CocoaPods' RubyGems installation method](https://guides.cocoapods.org/using/getting-started.html). Confirm `$TOOLCHAIN/gems/bin/pod` exists and runs with your prepared Ruby. The CLI handles `npm ci`, Expo prebuild, and `pod install` for each project during a build.

4. Install the Linux x86_64 server from [OpenAppleMacros v1.3.0](https://github.com/xtool-org/OpenAppleMacros/releases/tag/v1.3.0) as `apple-macros/OpenAppleMacrosServer`, and prepare the SDK-required plugin entry points. Prepare `host-macros/ExpoModulesMacros-tool` for the Linux host and the installed Expo version; do not copy a macOS executable from npm.
5. Supply compiler-compatible Darwin `Cxx`/`CxxStdlib` interfaces and shims in `darwin-resource`. After those resources, Clang, Swift, and the SDKs are present, generate the runtime objects and Swift/C++ overlay from the repository:

```sh
python3 ios_linux/scripts/prepare-runtime.py \
  --toolchain "$TOOLCHAIN" \
  --cxx-sources /path/to/swift-6.2/stdlib/public/Cxx
```

Replace the source path with the `stdlib/public/Cxx` directory from the official [Swift 6.2 release sources](https://github.com/swiftlang/swift/tree/swift-6.2-RELEASE). Rebuild the overlay when changing Swift. See [runtime preparation](toolchain.md#runtime-objects) for details.

**The experimental Ubuntu 24.04 Expo setup automates these steps.** Its full clean-machine bootstrap has not yet been validated; see [setup scope](setup.md#expo-setup). The manual commands above record the required inputs and layout.

**Godot-specific preparation**

Download the standard Linux x86_64 editor and matching export templates from the official [Godot 4.5.1 archive](https://godotengine.org/download/archive/4.5.1-stable/). Extract the editor and iOS templates, then place:

- The Linux editor executable at `$TOOLCHAIN/godot/godot`.
- The release **arm64 device** engine library at `$TOOLCHAIN/godot/libgodot.a`.
- Its matching MoltenVK library at `$TOOLCHAIN/godot/libMoltenVK.a`.

Use the device slices, not simulator slices, and keep the editor/template versions equal. See [Godot toolchain setup](toolchain.md#godot). Ruby/CocoaPods and Expo macros are not needed for the Godot backend.

**Optional: install onto a physical iPhone**

Install libimobiledevice's `ideviceinstaller` using your distribution's packages; on Ubuntu, `sudo apt-get install ideviceinstaller`. Set `installer` in the config if using a different executable path. This is needed for `ios-anywhere install`, not merely to produce an IPA. Device pairing and a matching provisioning profile are still required.

### 3. Configure paths and check the selected backend

Create a config without overwriting an existing one:

```sh
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/ios-anywhere"
mkdir -p "$CONFIG_DIR"
LEGACY_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/ios-linux/config.json"
if [ ! -e "$CONFIG_DIR/config.json" ] && [ ! -f "$LEGACY_CONFIG" ]; then
  cp config.example.json "$CONFIG_DIR/config.json"
fi
```

Edit your existing configuration, or `$CONFIG_DIR/config.json` (normally `~/.config/ios-anywhere/config.json`) for a new installation, to point `toolchain` at your prepared directory, and adjust `llvm_ar`/`installer` if needed. `TOOLCHAIN` above is a shell variable for setup commands; the CLI reads its toolchain path from this JSON file.

Run the check for the backend you prepared:

```sh
ios-anywhere --engine expo doctor
# Or, for Godot:
ios-anywhere --engine godot doctor
```

`doctor` checks required paths and commands; it does not install missing tools, download SDKs, or prove a successful build. Use `--config /path/to/config.json` to select another configuration. Activate the virtual environment or use `.venv/bin/ios-anywhere` directly.

**Validation scope:** a fresh checkout and virtual environment on an existing Debian 13.6 x86_64 host passed CLI installation and all 13 unit tests on October 16, 2026; that host already had Python, Node/npm, and OpenSSL. This did not install the external toolchain or build an IPA. A later user-run Godot build and device test on another PC succeeded after manually installing the USB utilities; see the dated second-PC test below. The updated automatic USB package installation has not yet been rerun there. See [device/build validation](validation.md) for the separately tested prepared environment.

If you already have an App Store IPA and only want to upload it, skip local compiler/toolchain setup and follow [Submit to Apple](../README.md#submit-to-apple).


## Configuration compatibility

Without `--config`, the CLI first looks for `ios-anywhere/config.json` under `XDG_CONFIG_HOME` (or `~/.config` when unset or empty). If it is absent, an existing `ios-linux/config.json` in that same root is used. When both exist, the new path wins; an invalid new file is reported rather than silently falling back. An explicit `--config` always takes precedence.

The quick-start copy command leaves both existing configurations untouched and does not create a new default that would hide a legacy configuration. No automatic migration occurs. If you manually copy a legacy configuration, check any relative paths because they are resolved relative to the selected JSON file.

For new installations, the example uses `~/.local/share/ios-anywhere/toolchain` and `~/.cache/ios-anywhere`. These are configured values, not discovery paths: existing JSON files keep their original toolchain and cache locations. Do not move or redownload a working toolchain merely to rename it. The `ios-linux` command alias, `ios_linux` Python module, and `IOS_LINUX_*` environment variables remain supported.

## Project layout

- `ios_linux/`: CLI, configuration, and backends.
- `ios_linux/scripts/`: shared compilation, graph export, and signing scripts.
- `examples/`: independent minimal Expo and Godot apps; change the Expo identity before signing.
- `tests/`: tests requiring no certificates, device, or Apple SDKs.
- External toolchain: `~/.local/share/ios-anywhere/toolchain`.
- Build cache: the config's `cache` path (`~/.cache/ios-anywhere` in the example config; `build-cache` beside the toolchain for guided setup). Contains source copies, resources, products, and logs. Do not share it: projects and configurations may contain private data.
- Local configuration: `~/.config/ios-anywhere/config.json`.

No project is selected implicitly. Builds do not depend on the working directory or clone location. CocoaPods generates absolute paths in the cache; rebuild after moving it. Do not move or delete the toolchain or cache during a build.

## Limitations

- Experimental, validated on Linux x86_64; not a universal Xcode replacement.
- Expo: SDK 54 validated with a standard Swift AppDelegate. Extensions, widgets, custom native phases, storyboards, and AppDelegates require additional support. Earlier project-specific widget work is not part of this distribution.
- Swift/C++ uses a separate compatibility overlay that must be rebuilt after the relevant CLI upgrade. Expo targets iOS 16.4 minimum; older devices have not been tested. Godot targets iOS 14.0 minimum, also without testing on older devices.
- Godot: GDScript and the standard engine without external plugins. C# and GDExtensions are rejected. This backend sets version/build to 1.0/1. Review game-specific privacy requirements before distribution.
- App Store: asset catalogs must already be compiled. Packaging preserves `Assets.car` and icons in `build/app-resources`; generating PNGs alone does not meet Apple's asset catalog requirement.
- The toolchain is installed separately. Apple SDKs, external libraries, and credentials are not distributed in this repository.
