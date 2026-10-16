# Guided toolchain setup

Install the Python CLI first, activate its virtual environment, then run:

```sh
ios-anywhere setup
```

The default assistant prepares **Godot 4.5.1 on Linux x86_64**, using system Clang 18, the Darwin linker, Godot's device libraries, an iPhoneOS 18.5 SDK, and zsign-wasm. For the experimental Expo recipe on Ubuntu 24.04, see [Expo setup](#expo-setup) below.

## What happens

1. Choose a local SDK folder or the unofficial mirror described below.
2. Review destination paths and approve downloads. Missing system commands, including `ideviceinstaller`, `libimobiledevice-utils` and `usbmuxd` for iPhone installation, can be installed with apt; non-root users need sudo. Other distributions must provide the listed packages themselves.
3. Download and verify the linker, Godot editor, and export templates. Install only the release arm64 device libraries from the templates.
4. Import/download the SDK and install zsign-wasm 0.0.4 through npm, with lifecycle scripts disabled.
5. Run the editor, compile C/C++ support, link a native Godot executable, and load the signer. Publish the toolchain and config only after these checks pass.

No certificate is needed for setup. Signing and device installation remain separate. A successful setup is **not** proof that an app launches on an iPhone or passes Apple's validation.

Setup requires at least **8 GiB free on the destination filesystem before downloading**, plus space for system packages and later builds. This is a conservative preflight threshold, not a measured maximum. It downloads the full 1.35 GB Godot templates archive, but extracts only the iOS device libraries. Do not run it on a nearly full disk.

## SDK choices

- **Local:** provide an extracted `iPhoneOS18.5.sdk` folder. Setup checks its version, essential files, and that symlinks stay inside it. It copies the SDK without changing the source.
- **Mirror:** explicitly choose `xybp888/iOS-SDKs`, pinned to commit `ad607cb07fe4ad1c9b91cf970bd228c2a9253207`. Setup fetches that revision and sparsely checks out `iPhoneOS18.5.sdk`. This is an **unofficial source**, not an Apple-authenticated download. A pinned revision establishes which mirror contents are used; it does not establish authenticity or grant an SDK license.

The official SDK source is [Apple's Xcode downloads](https://developer.apple.com/download/all/). Apple SDK terms remain applicable to either source. The assistant does not import `.xip` files yet.

## Unattended installation

Choose the SDK source explicitly; `--yes` alone never selects a mirror:

```sh
# Download the pinned unofficial SDK; accept downloads and missing apt packages.
ios-anywhere setup --engine godot --sdk-source mirror --yes

# Or import a local SDK.
ios-anywhere setup --sdk-source local --sdk /path/to/iPhoneOS18.5.sdk --yes
```

To test without touching an existing installation, use **both** a new configuration file and a new toolchain directory:

```sh
ios-anywhere --config "$HOME/.config/ios-anywhere/godot-test.json" \
  setup --toolchain /path/on/large-disk/godot-toolchain \
  --sdk-source mirror --yes

ios-anywhere --config "$HOME/.config/ios-anywhere/godot-test.json" \
  --engine godot doctor
```

Existing configs, toolchain directories, and dangling symlinks are rejected. Setup does not migrate, merge, or replace them. For a new install, the default config follows the CLI's XDG/legacy config selection; the default toolchain is `~/.local/share/ios-anywhere/toolchain`.

## Retries and provenance

Binary release downloads use pinned SHA-256 hashes from their upstream GitHub releases:

- [Darwin tools v1.1.0](https://github.com/xtool-org/darwin-tools-linux-llvm/releases/tag/v1.1.0).
- [Godot 4.5.1](https://github.com/godotengine/godot-builds/releases/tag/4.5.1-stable).

Downloads are kept in `.<toolchain-name>-downloads` beside the toolchain. Complete files are rechecked before reuse; partial HTTP downloads are resumed. SDK checkout, extraction, and npm installation restart on failure. A failed attempt removes its temporary staging directory; it does not roll back installed system packages. Abrupt process termination may leave staging files behind. Never remove another running setup's files.

After success, you may delete that download cache while no setup is running. Keep the toolchain itself. `setup-manifest.json` records the selected source/revision and release hashes; the signer's package lock is kept in `signing/`. Clang 18 remains a system dependency. npm transitive dependencies and apt packages are not a fully locked operating-system image.

## Validation status

The setup flow has automated tests for checksum failures, download reuse, low disk space, SDK validation, preservation of existing paths, and publishing only after a successful native check. On October 16, 2026, all 34 repository tests passed; the official Godot template's device-library paths were inspected directly, and the pinned linker archive was downloaded, checksum-verified, and extracted. The native check passed with system Clang 18 and the existing prepared SDK/Godot libraries; the signer also loaded successfully.

End-to-end installation and a signed IPA from a blank machine are **not yet validated**. The local disk had approximately 2.3 GiB free, below the setup threshold. The setup is experimental; report failures with the step and tool versions, without sharing credentials.

## Existing installations missing USB utilities

Do not rerun setup into an existing toolchain. Install the missing packages, then pair the unlocked iPhone:

```sh
sudo apt-get update
sudo apt-get install -y ideviceinstaller libimobiledevice-utils usbmuxd
idevicepair pair
```

No rebuild is needed for an already signed IPA.

## Expo setup

The experimental Expo recipe requires **Ubuntu 24.04 x86_64**, Python 3.11.8+ or 3.12+, and **20 GiB free before downloads**, plus room for your project and build cache. It installs system packages through apt (sudo may be required). It does not use a previously built app or copy another project's native code.

On a new installation:

```sh
ios-anywhere setup --engine expo
```

If a Godot or other toolchain already exists, keep it and choose **both** a new config and a new toolchain directory:

```sh
ios-anywhere --config "$HOME/.config/ios-anywhere/expo.json" \
  setup --engine expo \
  --toolchain "$HOME/.local/share/ios-anywhere/expo-toolchain"

ios-anywhere --config "$HOME/.config/ios-anywhere/expo.json" --engine expo doctor
```

Use that same `--config` before `build` when building an Expo project. Setup does not merge toolchains or change your default config when an explicit new path is used.

Choose the pinned unofficial SDK mirror interactively, or pass `--sdk-source mirror --yes`. For local SDKs, pass `--sdk-source local --sdk /path/to/sdks`; that folder must contain **both** `iPhoneOS26.4.sdk` and `iPhoneOS26.5.sdk`. The mirror-only UIKitCore workaround is applied only after checking the known file hash; local SDKs are not patched.

The recipe installs:

- Swift 6.4.0 for Ubuntu 24.04, Node 22.20.0, Darwin tools v1.1.0, and OpenAppleMacros v1.3.0 from versioned, SHA-256-checked downloads.
- System Ruby 3.2 and CocoaPods 1.17.0. The Ruby layout points to Ubuntu's `/usr`; this toolchain cannot be moved to another OS without preparing those packages.
- Expo macros 0.6.1 compiled for Linux using SwiftCompilerPlugin from swift-syntax commit `050f1a346fbbac0ca2cfb15a95274f7bd1cf0ccf`.
- Darwin C++ interfaces adapted from the installed compiler, and a compatibility overlay rebuilt from Swift 6.2 commit `1ff1cc1170617ab23ab74aa8b741c8daca1903f6`.
- npm zsign-wasm 0.0.4 and the iPhone USB utilities. Apple credentials are still supplied separately.

The SDKs use the same pinned revision documented above. npm package versions and CocoaPods itself are pinned; their transitive dependencies and apt packages are not a fully reproducible lock. CocoaPods installation compiles dependencies and runs RubyGems installation hooks. Projects needing a different Expo macro implementation may need adaptation.

Before publishing the toolchain, setup checks CocoaPods, compiles a UIKit Swift probe, links an arm64 Mach-O executable, and loads the signer. This is **not a full React Native app build**, a device launch, or App Store validation. Failures leave existing installations intact; verified download caches are retained for retries. No credentials are read during setup.

Validation: SDK-free tests cover engine routing, publication only after checks pass, disk requirements, archive traversal rejection, overlay isolation, Node selection, and the mirror patch guard. Component checks use an existing compiler/SDK installation; the complete download-and-install recipe still needs a clean Ubuntu 24.04 test.
