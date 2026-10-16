# Architecture

`cli.py` validates arguments, checks configuration, and prevents concurrent builds in the same cache. `config.py` knows only the toolchain and cache; no project is stored as a default.

`expo.py` resolves dependencies and graphs inside an isolated project copy. Scripts receive `IOS_LINUX_PROJECT`, `IOS_LINUX_BUILD`, and `IOS_LINUX_TOOLCHAIN` explicitly. Clang/Ruby wrappers and the Xcode project exporter ship with the package; SDKs and executables remain external resources.

`godot.py` copies the project, exports a PCK, and links generic engine libraries. It does not use a previously exported project as a template. `templates/` contains only minimal native support and the standard Godot privacy manifest, with attribution preserved.

`signing.py` accepts the same credentials format for both backends. It signs an `.app` directory, produces a temporary IPA, verifies it, and writes the final file without overwriting existing files. Passwords are not stored in the repository, process arguments, or reports.

Installation uses locally configured libimobiledevice. IPA verification requires Python and OpenSSL, but no toolchain or login. Reports do not automatically claim device validation.

## Migration from the laboratory version

Version 0.2 removed implicit projects, fixed profiles, personal-account provisioning, and `--workspace`. Configure `--config`, always supply `--project`, and provide `--credentials` for Godot as well. The standalone `package` command was removed to prevent accidental signing of stale products; use `build`. Use `verify` to inspect existing IPAs.

Never use the original source tree as the compilation output directory. Project settings that reference paths outside the copy or use custom Xcode build phases may require adaptation. The CLI executes trusted projects; it is not a sandbox for third-party code.
