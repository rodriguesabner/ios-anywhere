# External toolchain

The CLI is independent of application projects, but bootstrapping a clean machine **is still manual**. This repository does not automatically download Apple SDKs or distribute toolchain binaries. Obtain SDKs through permitted means and check each tool's license.

## Expected layout

The configuration's `toolchain` field points to a directory containing:

```text
toolchain/
  swift/usr/bin/{swiftc,clang,clang++}
  darwin-tools/bin/ld64.lld
  sdks/{iPhoneOS18.5.sdk,iPhoneOS26.4.sdk,iPhoneOS26.5.sdk}/
  darwin-resource/
    clang -> ../swift/usr/lib/clang/21
    shims -> ../swift/usr/lib/swift/shims
    iphoneos/{Cxx.swiftmodule,CxxStdlib.swiftmodule,libcxxshim.h,libcxxshim.modulemap,libcxxstdlibshim.h}
  ruby/usr/bin/ruby3.2
  ruby/usr/lib/...
  gems/{bin/pod,gems/...}
  apple-macros/{OpenAppleMacrosServer,plugins/...}
  host-macros/ExpoModulesMacros-tool
  os_version_check.o
  cxx-runtime/{compat-markers.o,Cxx.o,modules/Cxx.swiftmodule/...}
  signing/{package.json,package-lock.json,node_modules/zsign-wasm/...}
  godot/{godot,libgodot.a,libMoltenVK.a}
```

`llvm_ar` and `installer` accept an executable on PATH or an absolute path. Optional `installer_lib` sets `LD_LIBRARY_PATH` only for libimobiledevice. Keep credentials outside the toolchain and repository.

## Components in the validated environment

| Component | Source/version | Purpose |
| --- | --- | --- |
| Swift Linux | Swift 6.4 RELEASE | Swift, Clang, and shims |
| Mach-O linker | [darwin-tools-linux-llvm v1.1.0](https://github.com/xtool-org/darwin-tools-linux-llvm/releases/tag/v1.1.0) | `ld64.lld` |
| Apple macros on Linux | [OpenAppleMacros v1.3.0](https://github.com/xtool-org/OpenAppleMacros/releases/tag/v1.3.0) | Swift plugin server |
| iOS SDK | 18.5, 26.4, and 26.5 | Godot; Expo compilation; Expo linking, respectively |
| Ruby/CocoaPods | Ruby 3.2, CocoaPods 1.17.0 | Pod resolution and project export |
| Expo macros | Linux plugin compiled for the installed Expo version | `host-macros/ExpoModulesMacros-tool` |
| Signer | npm `zsign-wasm@0.0.4` | Local signing |
| Godot | Linux editor 4.5.1 + iOS release arm64 libraries 4.5.1 | PCK and engine |
| LLVM ar | LLVM 18 in the tested environment | Static archives |

Darwin `Cxx`/`CxxStdlib` files must match the compiler. The Linux Swift toolchain alone does not include every required Apple overlay. The macros directory contains the Linux server and plugin entry points expected by SDK interfaces. Build Expo macros for the host; do not copy a macOS executable from npm. These are real prerequisites, not installed by `doctor`.

The tested SDK set came from the `xybp888/iOS-SDKs` mirror, revision `ad607cb07fe4ad1c9b91cf970bd228c2a9253207`. In that mirror's SDKs 26.5 and 27, `System/Library/PrivateFrameworks/UIKitCore.framework/UIKitCore.tbd` was disabled by renaming it to `.tbd.mirror-backup`: the incomplete private stub overrode the public one. This workaround is specific to that set; do not apply it to another SDK without investigation. Expo uses SDK 26.4 for C/Swift compilation and 26.5 for linking. The mirror's 26.4 stubs omit Swift symbols in public frameworks, including StoreKit. The pipeline no longer selects SDK 27.

To prepare the signer alone in an external directory, set `TOOLCHAIN` to your toolchain path and run:

```sh
npm install --prefix "$TOOLCHAIN/signing" --save-exact zsign-wasm@0.0.4
```

The Python package includes CLI scripts. RubyGem scripts should use `#!/usr/bin/env ruby` to avoid paths from a previous machine. The backend configures Ruby, GEM_HOME, GEM_PATH, and compilation wrappers per process.

## Runtime objects

Once the compiler and SDKs are available:

```sh
python3 ios_linux/scripts/prepare-runtime.py --toolchain "$TOOLCHAIN"
```

For Swift/C++ projects, provide [Swift 6.2 Cxx sources](https://github.com/swiftlang/swift/tree/swift-6.2-RELEASE/stdlib/public/Cxx):

```sh
python3 ios_linux/scripts/prepare-runtime.py \
  --toolchain "$TOOLCHAIN" \
  --cxx-sources /path/to/swift-6.2/stdlib/public/Cxx
```

The overlay is isolated in `cxx-runtime/modules`; the compiler's default overlay is preserved. The overlay targets iOS 16.4. Rerun this command when upgrading from an installation whose overlay targeted iOS 27. This does not replace runtime testing on older devices. The combination avoids references to `Swift.Iterable`, which the tested device did not provide. Binary modules are not universal across compilers: rebuild when changing Swift.

## Godot

Obtain the Linux editor and official iOS template of the same version. Put the editor at `godot/godot`, the release **arm64 device** library at `godot/libgodot.a`, and the matching MoltenVK library at `godot/libMoltenVK.a`. Do not use simulator slices. The CLI generates its own minimal native support; it needs no earlier exported game or copied game assets.

## Portability and cleanup

The toolchain directory can be moved if configuration and internal links are updated. Clone and application paths are not used as fallbacks. `doctor` detects missing required files but cannot replace a real build to evaluate version compatibility.

A project's cache can be deleted while all builds are stopped; the next build regenerates dependencies, graphs, and modules. The toolchain is durable infrastructure, not a project cache. Never delete it to clean build outputs.
