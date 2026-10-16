# Guided Godot setup

Install the Python CLI first, activate its virtual environment, then run:

```sh
ios-anywhere setup
```

The current assistant prepares **Godot 4.5.1 on Linux x86_64**, using system Clang 18, the Darwin linker, Godot's device libraries, an iPhoneOS 18.5 SDK, and zsign-wasm. Expo's Swift/macros/Ruby setup is still [manual](installation.md). Requesting `setup --engine expo` exits without changing files.

## What happens

1. Choose a local SDK folder or the unofficial mirror described below.
2. Review destination paths and approve downloads. Missing system commands can be installed with apt; non-root users need sudo. Other distributions must provide the listed packages themselves.
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
