# Third-party components

- `ios_linux/templates/dummy.cpp`: Godot Engine, MIT license and attribution preserved in the header.
- `ios_linux/templates/PrivacyInfo.xcprivacy`: standard privacy manifest from the Godot Engine iOS template (MIT).
- `ios_linux/scripts/os_version_check.c`: LLVM compiler-rt; copyright and license notice preserved in the header.
- `examples/expo-counter/package-lock.json`: npm dependency versions; packages are not included.

Swift, Apple SDKs, Godot/MoltenVK, Ruby, CocoaPods, LLVM, macros, and zsign-wasm are external dependencies, not redistributed in this repository. Their licenses and requirements remain applicable. A private repository grants no rights to external SDKs or libraries.

The experimental Godot setup downloads upstream Godot 4.5.1 and Darwin tools v1.1.0 releases, installs system Clang 18 and npm zsign-wasm 0.0.4, and optionally fetches the unofficial xybp888/iOS-SDKs mirror at a pinned revision. Source selection, checksums, and limits are documented in [guided setup](docs/setup.md). Choosing a mirror does not grant additional rights or establish Apple authenticity.

## Preserved license texts

- [Godot MIT license](licenses/Godot.txt), from [Godot 4.5.1](https://github.com/godotengine/godot/blob/4.5.1-stable/LICENSE.txt), covers the Godot-derived templates listed above. The source header in `dummy.cpp` is retained.
- [LLVM compiler-rt license](licenses/LLVM-compiler-rt.txt), from [LLVM compiler-rt](https://github.com/llvm/llvm-project/blob/main/compiler-rt/LICENSE.TXT), includes Apache 2.0 with LLVM exceptions and historical licensing information. The SPDX notice in `os_version_check.c` is retained.

The project's MIT license does not replace either third-party license.

The experimental Expo setup downloads Swift 6.4.0 (Swift.org), Node 22.20.0 (Node.js), OpenAppleMacros v1.3.0, and SwiftCompilerPlugin source (swift-syntax). It installs CocoaPods 1.17.0 and Expo macros 0.6.1, and rebuilds the Cxx overlay from the pinned Swift 6.2 sources. Source license headers remain in downloaded files; no external binaries are committed here. See [Expo setup](docs/setup.md#expo-setup) for revisions, dependency locking limits, and host requirements.

The interactive terminal menu uses [Questionary](https://github.com/tmbo/questionary) (MIT), installed as a Python dependency. Its dependencies retain their own licenses. No Questionary source is vendored here.
