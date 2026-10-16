# Third-party components

- `ios_linux/templates/dummy.cpp`: Godot Engine, MIT license and attribution preserved in the header.
- `ios_linux/templates/PrivacyInfo.xcprivacy`: standard privacy manifest from the Godot Engine iOS template (MIT).
- `ios_linux/scripts/os_version_check.c`: LLVM compiler-rt; copyright and license notice preserved in the header.
- `examples/expo-counter/package-lock.json`: npm dependency versions; packages are not included.

Swift, Apple SDKs, Godot/MoltenVK, Ruby, CocoaPods, LLVM, macros, and zsign-wasm are external dependencies, not redistributed in this repository. Their licenses and requirements remain applicable. A private repository grants no rights to external SDKs or libraries.

## Preserved license texts

- [Godot MIT license](licenses/Godot.txt), from [Godot 4.5.1](https://github.com/godotengine/godot/blob/4.5.1-stable/LICENSE.txt), covers the Godot-derived templates listed above. The source header in `dummy.cpp` is retained.
- [LLVM compiler-rt license](licenses/LLVM-compiler-rt.txt), from [LLVM compiler-rt](https://github.com/llvm/llvm-project/blob/main/compiler-rt/LICENSE.TXT), includes Apache 2.0 with LLVM exceptions and historical licensing information. The SPDX notice in `os_version_check.c` is retained.

The project's MIT license does not replace either third-party license.
