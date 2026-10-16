<div align="center">

# ios-anywhere

### From your project to your iPhone. Built locally on Linux.

**Expo · Godot · Compile · Sign · Install**

![Status: experimental](https://img.shields.io/badge/status-experimental-f0b429)
![Host: Linux x86_64](https://img.shields.io/badge/host-Linux_x86__64-20252b)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)

[Quick start](#installation) · [Expo](#expo) · [Godot](#godot) · [Compatibility](#compatibility) · [Submit to Apple](#submit-to-apple) · [Documentation](#documentation)

</div>

---

An experimental CLI to compile, sign, and install iOS apps **locally on Linux**, with **Expo** and **Godot** backends. Builds run without a Mac or EAS Build. The Expo backend still uses the local Expo CLI for prebuild and JavaScript bundling.

Each build receives an explicit project, its own credentials, and an output path. Compilers, SDKs, and caches live outside this repository. No previous application is required as a template.

```text
Expo / Godot project → local compilation → signing → IPA → iPhone
```

## Compatibility

| Workflow | Current status |
| --- | --- |
| Expo | SDK 54 examples built and tested on iPhone; native dependencies may need adaptation. |
| Godot | GDScript with engine 4.5.1; examples built and tested on iPhone. |
| Signing | Valid certificate and provisioning profile supplied by the user. |
| Widgets and extensions | Not supported by the generic CLI workflow yet. |
| App Store | Experimental; upload does not prove processing or approval. Precompiled assets are still required. |
| Host systems | Linux x86_64 validated. Windows and macOS have not been validated. |

See [Validation](docs/validation.md) for evidence and test scope.

## Installation

Requires Python 3.11+, Node/npm, OpenSSL, and Pillow. Install from this repository:

```sh
git clone https://github.com/rodriguesabner/ios-anywhere.git
cd ios-anywhere
python3 -m venv .venv
.venv/bin/pip install .
. .venv/bin/activate
ios-anywhere --version
```

Prepare the [external toolchain](docs/toolchain.md), copy `config.example.json` to `~/.config/ios-linux/config.json`, and adjust the paths. **Installing the Python package does not install compilers, SDKs, or Apple credentials.**

```sh
ios-anywhere doctor
ios-anywhere --engine godot doctor
```

Use `--config /path/to/config.json` to select another configuration. Activate the virtual environment or use `.venv/bin/ios-anywhere` directly.

## Expo

```sh
ios-anywhere --engine expo \
  --project /path/to/my-app \
  --credentials /private/credentials.json \
  build --output /path/to/MyApp-01.ipa
```

The project needs `package.json`, `package-lock.json`, and an Expo configuration with `ios.bundleIdentifier`. The CLI creates an isolated copy, runs `npm ci`, iOS prebuild and CocoaPods, exports the app's build graphs, compiles native modules, generates Hermes bytecode, and signs the IPA. The original source is not modified. Project scripts and npm packages execute during this process: use trusted sources.

## Godot

```sh
ios-anywhere --engine godot \
  --project /path/to/my-game \
  --bundle-id com.example.mygame \
  --credentials /private/credentials.json \
  build --output /path/to/MyGame-01.ipa
```

The source directory must contain `project.godot`. The backend exports a fresh PCK, links the iOS arm64 engine installed in the toolchain, and applies the project's identity, name, orientation, and PNG icon. Match editor and engine versions; the validated environment uses Godot 4.5.1.

## Signing, verification, and installation

Use the format in [credentials.example.json](credentials.example.json). Certificate and profile paths can be absolute or relative to the credentials file. For direct device installation, the profile must match the app identity and include the device. Supply your certificate, password, and profile; the CLI does not sign in to Apple or create profiles automatically.

```sh
ios-anywhere verify /path/to/MyApp-01.ipa
ios-anywhere install /path/to/MyApp-01.ipa --udid YOUR_UDID
```

`verify` checks code and resource hashes, the CMS signature, and profile correspondence. It does not check Apple's trust or revocation status, establish App Store compatibility, or prove runtime behavior. `IOS_LINUX_UDID` can restrict verification to the intended device.

`build` writes the final IPA only after signing and verification. Existing output files are rejected. Installation is separate. `bundle` prepares resources without signing. Global options (`--project`, `--credentials`, `--engine`, `--config`) precede the subcommand.

## Submit to Apple

Upload an existing production IPA through **EAS Submit**, from your app's EAS-configured project directory:

```sh
npx eas-cli login
npx eas-cli submit --platform ios --profile production --path /path/to/MyApp-AppStore.ipa
```

Configure the destination in the app's `eas.json`, merging this section with any existing configuration:

```json
{
  "submit": {
    "production": {
      "ios": {
        "ascAppId": "YOUR_NUMERIC_APP_STORE_CONNECT_APP_ID"
      }
    }
  }
}
```

Use an App Store distribution certificate/profile and a new build number for that app version. An Ad Hoc IPA intended for direct installation is not a store submission artifact. Complete Apple authentication when prompted, or configure your own App Store Connect API key using `ascApiKeyPath`, `ascApiKeyId`, and `ascApiKeyIssuerId` in the submission profile. Keep keys outside version control.

This uses Expo's submission service, not EAS Build. The CLI has no built-in `submit` command. Uploading sends the binary to App Store Connect; Apple processing, TestFlight availability, and submission for App Review are separate steps. Asset catalogs and current Apple requirements must still be satisfied.

Sources: [EAS Submit for iOS](https://docs.expo.dev/submit/ios/), [submitting an existing IPA](https://docs.expo.dev/deploy/submit-to-app-stores/).

## Project layout

- `ios_linux/`: CLI, configuration, and backends.
- `ios_linux/scripts/`: shared compilation, graph export, and signing scripts.
- `examples/`: independent minimal Expo and Godot apps; change the Expo identity before signing.
- `tests/`: tests requiring no certificates, device, or Apple SDKs.
- External toolchain: `~/.local/share/ios-linux/toolchain`.
- Disposable cache: `~/.cache/ios-linux`, containing source copies, resources, products, and logs. Do not share it: projects and configurations may contain private data.
- Local configuration: `~/.config/ios-linux/config.json`.

No project is selected implicitly. Builds do not depend on the working directory or clone location. CocoaPods generates absolute paths in the cache; rebuild after moving it. Do not move or delete the toolchain or cache during a build.

## Limitations

- Experimental, validated on Linux x86_64; not a universal Xcode replacement.
- Expo: SDK 54 validated with a standard Swift AppDelegate. Extensions, widgets, custom native phases, storyboards, and AppDelegates require additional support. Earlier project-specific widget work is not part of this distribution.
- Swift/C++ uses a separate compatibility overlay that must be rebuilt after the relevant CLI upgrade. Expo targets iOS 16.4 minimum; older devices have not been tested. Godot targets iOS 14.0 minimum, also without testing on older devices.
- Godot: GDScript and the standard engine without external plugins. C# and GDExtensions are rejected. This backend sets version/build to 1.0/1. Review game-specific privacy requirements before distribution.
- App Store: asset catalogs must already be compiled. Packaging preserves `Assets.car` and icons in `build/app-resources`; generating PNGs alone does not meet Apple's asset catalog requirement.
- The toolchain is installed separately. Apple SDKs, external libraries, and credentials are not distributed in this repository.

## Development

```sh
python3 -m unittest discover -s tests -v
```

See [Validation](docs/validation.md) for real-world checks and [Architecture](docs/architecture.md) for boundaries between source, tools, and builds.

## FAQ

**Do I need a Mac to run this workflow?** Not in the prepared Linux environment. The external toolchain and SDKs are prerequisites; the Python package does not install them.

**Do I need EAS Build?** No. The Expo backend uses local Expo ecosystem tools. Store submission is a separate step.

**Does it work with every app?** No. Projects with different native requirements need their own validation.

**Can I skip Apple signing credentials?** No. The CLI signs with your credentials and respects provisioning profile restrictions.

## Documentation

- [Toolchain setup](docs/toolchain.md)
- [Architecture and project isolation](docs/architecture.md)
- [Validation and device tests](docs/validation.md)
- [Third-party components](THIRD_PARTY.md)
- [Website creation prompt](docs/website-prompt.md)
- [AI agent guide](llm.txt)

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md) for responsible-use guidance covering all ios-anywhere versions, platforms, and distribution channels. Each copy retains its applicable licenses.

The project is intended for development, research, education, interoperability, and preservation of software you own or are authorized to use, modify, and distribute. Signing requires valid credentials; the CLI grants no distribution rights or App Store approval.

## Contributing

Contributions are welcome! [Open an issue](https://github.com/rodriguesabner/ios-anywhere/issues) to report a bug or suggest a feature, or [send a pull request](https://github.com/rodriguesabner/ios-anywhere/pulls) to improve the code or docs. Access requires permission to this private repository.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and checks, [Validation](docs/validation.md) for test scope, and [Architecture](docs/architecture.md) for project structure.

## License

Project-authored code is licensed under [MIT](LICENSE). Third-party material retains its own licenses and copyright notices; see [Third-party components](THIRD_PARTY.md).

**You must legally obtain and be authorized to use external tools and SDKs**, including Apple SDKs and toolchain dependencies, under their applicable terms. ios-anywhere grants no tool license, key, or activation entitlement. Unauthorized copies, stolen keys, unauthorized credential sharing, and bypassing license restrictions are not authorized by the project. This guidance does not amend MIT or third-party licenses.
