# Validation

Initial manual build and device checks were performed on 2026-10-15, Linux x86_64. Later checks are dated separately.

## Automated checks and badge scope

The [Unit tests workflow](../.github/workflows/tests.yml) installs the Python package on Ubuntu with Python 3.11 and Node.js 22, then runs:

```sh
python -m pip install .
python -m unittest discover -s tests -v
python -m compileall -q ios_linux tests
```

Node.js is needed by the Expo module-resolution test. The workflow needs no Apple SDK, certificate, provisioning profile, device, or repository secret. Its token has read-only repository-content access. It runs on pushes and pull requests; the README's live badge is limited to push runs on `main`. A missing or not-yet-run badge is not a successful result.

A passing run covers the unit suite and Python compilation only, not an iOS build, signing, device execution, or Apple acceptance. The manual badges in the README are static links to the dated evidence below; they are not CI checks and do not establish that every later commit was tested on a device.

## Version 0.2 refactoring

- 13 automated tests passed: explicit input, credentials required for both engines, existing-output protection, verification failure preventing final output, Godot isolation, identity/orientation, internal/external npm resolution, and Expo adaptations.
- Python static checks passed (`ruff check --select F` and `compileall`).
- A Python wheel was built and installed; both engines' `doctor` commands ran from another directory.
- Minimal Expo SDK 54 app: npm, prebuild, pods, JS/Hermes, Swift modules, 81 C/ObjC/C++ sources, linking, signing, and verification passed in a fresh cache outside the clone and earlier workspace.
- Minimal Godot 4.5.1 app: import, PCK export, support compilation, linking, signing, and verification passed through the installed package. Generic toolchain libraries were used; no earlier game was a dependency.
- The verifier accepted the Godot IPA and rejected a copy with a modified PCK.
- Fresh Expo graphs and build commands were checked for references to the earlier workspace.
- Code was reviewed to exclude personal paths, certificates, passwords, Apple sessions, SDKs, and IPAs from publication.

## Device tests

On 2026-10-15, **Expo-Portable-01** and **Godot-Portable-01**, produced after the refactoring, were installed on an iPhone. The user confirmed that both examples opened and worked.

This validates the minimal examples on the tested device. It is not exhaustive testing of other projects, native dependencies, purchases, or ads.

## Not verified

Full bootstrap on a clean machine; other compiler/SDK combinations; Linux arm64; older iOS versions; purchases, ads, Apple processing, TestFlight availability, App Review, and App Store publication. Upload to Apple has been tested separately; see the CS Callouts example below. Local CMS verification does not query Apple trust or revocation status.

## Distribution metadata and version 0.2.1

- The Expo backend records device family and the SDK actually used for linking without inventing an Xcode version.
- Packaging preserves precompiled asset catalogs and icons. Generating Assets.car on Linux has not been implemented.
- Upload to Apple was tested with CS Callouts; see the result and scope below.
- All 13 automated tests passed again, including metadata and icon preservation checks.
- The public name became ios-anywhere. The previous command, Python module, and configuration paths were preserved.

## Apple upload example: CS Callouts

The CS Callouts experiment uploaded an IPA to Apple containing a Linux-built executable and an asset catalog reused from an EAS build of the same app. This is a completed upload test, not merely a proposed submission workflow.

The documented result establishes the upload stage. Apple processing, TestFlight availability, submission for App Review, review approval, and App Store publication have not been verified. The reused asset catalog also means this experiment does not validate generating Assets.car on Linux.

See the [submission commands and requirements](../README.md#submit-to-apple).

## Continuous Expo demonstration

On 2026-10-15, Expo-Demo-04 was compiled through the installed CLI, signed with the app's Apple distribution credentials, verified, and installed on the connected iPhone (InstallComplete 100%). The user opened the sample and incremented the counter to 17, visible in the final capture.

The 3 min 41 sec recording is continuous, with no pauses or cuts. Credential acquisition is explained rather than executed; the build and installation are real. The website copy has no audio. This device test does not validate App Store processing or arbitrary native dependencies.

## Second-PC Godot test — 2026-10-16

The user ran guided setup on another PC and built the upstream [Truck Town demo](https://github.com/godotengine/godot-demo-projects/tree/master/3d/truck_town). The CLI reported a signed and verified IPA; installation reached `InstallComplete (100%)`, and the user supplied a screenshot of the running game. The exact demo commit and host distribution were not recorded.

The first install attempt exposed missing USB dependencies. Installing `ideviceinstaller`, `libimobiledevice-utils`, and `usbmuxd` resolved it. Setup now includes those packages, with a regression test; the updated setup itself has not been rerun end to end on that host. Signing used an existing distribution certificate and an Ad Hoc profile containing the device, with the exact bundle ID authorized by that profile.

## Expo setup component checks — 2026-10-16

The Ubuntu 24.04 recipe was implemented with staged publishing and pinned Swift, Node, linker, Apple macro, SwiftCompilerPlugin, and SDK sources. The complete fresh-machine setup has **not** been run.

Using the existing Swift 6.4 compiler and SDKs, the new recipe successfully regenerated Darwin interfaces and the Swift 6.2 Cxx runtime objects, rebuilt the Expo macro plugin, and resolved its libraries after relocating its staging directory. Its smoke check ran CocoaPods, compiled a UIKit Swift probe, linked an arm64 Mach-O executable, and loaded zsign-wasm. Temporary compilation products were removed after these checks.

The Swift archive checksum was calculated by streaming the official download without saving a second toolchain. Automated tests cover setup routing, required free space, safe extraction, SDK patch guards, isolated overlays, local Node selection, and withholding the final config/toolchain after a failed smoke check. These results do not establish a complete Expo app build with freshly installed apt/RubyGems/npm dependencies or runtime compatibility on an iPhone.


## Expo 53 native dependency regression checks

The Linux backend repairs failed glog pthread/pread configure probes (missing `dsymutil`), treats glog's umbrella as textual headers without inferred submodules, and expands recursive CocoaPods header search paths. For fmt 11.0, it enables an explicit `FMT_USE_CONSTEVAL=0` override to avoid a reproduced upstream-Clang/Apple-SDK constant-evaluation failure; formatting remains available, but compile-time format validation is reduced.

Checked locally with the installed iOS toolchain: seven glog 0.3.5 source files compile; the namespace/module failure reproduces before and passes after the module-map change; fmt 11.0.2 `format.cc` fails before and compiles after the override; Skia 2.0.0 `base64.cpp` compiles with expanded recursive include paths. Cached glog configuration recovery was also exercised. These component checks do not establish a complete Expo app build, successful linking, or device execution.
