# Validation

Performed on 2026-10-15, Linux x86_64.

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

Full bootstrap on a clean machine; other compiler/SDK combinations; Linux arm64; older iOS versions; purchases, ads, and App Store distribution. Local CMS verification does not query Apple trust or revocation status.

## Distribution metadata and version 0.2.1

- The Expo backend records device family and the SDK actually used for linking without inventing an Xcode version.
- Packaging preserves precompiled asset catalogs and icons. Generating Assets.car on Linux has not been implemented.
- The CS Callouts experiment uploaded an IPA containing a Linux-built executable and an asset catalog reused from an EAS build of the same app. Completed upload does not confirm Apple processing or approval; that final confirmation was not verified.
- All 13 automated tests passed again, including metadata and icon preservation checks.
- The public name became ios-anywhere. The previous command, Python module, and configuration paths were preserved.

## Continuous Expo demonstration

On 2026-10-15, Expo-Demo-04 was compiled through the installed CLI, signed with the app's Apple distribution credentials, verified, and installed on the connected iPhone (InstallComplete 100%). The user opened the sample and incremented the counter to 17, visible in the final capture.

The 3 min 41 sec recording is continuous, with no pauses or cuts. Credential acquisition is explained rather than executed; the build and installation are real. The website copy has no audio. This device test does not validate App Store processing or arbitrary native dependencies.
