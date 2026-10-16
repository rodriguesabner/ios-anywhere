<div align="center">

# ios-anywhere

### From your project to your iPhone. Built locally on Linux.

**Expo · Godot · Compile · Sign · Install**

![Status: experimental](https://img.shields.io/badge/status-experimental-f0b429)
![Host: Linux x86_64](https://img.shields.io/badge/host-Linux_x86__64-20252b)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)

[![Unit tests (live CI on main)](https://github.com/rodriguesabner/ios-anywhere/actions/workflows/tests.yml/badge.svg?branch=main&event=push)](https://github.com/rodriguesabner/ios-anywhere/actions/workflows/tests.yml?query=branch%3Amain)
[![Expo device: documented manual test](https://img.shields.io/badge/Expo_device-documented_manual_test-007ec6)](docs/validation.md#device-tests)
[![Godot device: documented manual test](https://img.shields.io/badge/Godot_device-documented_manual_test-007ec6)](docs/validation.md#device-tests)
[![Apple upload: documented manual test](https://img.shields.io/badge/Apple_upload-documented_manual_test-007ec6)](docs/validation.md#apple-upload-example-cs-callouts)

[Website](https://rodriguesabner.github.io/ios-anywhere/) · [Quick start](#installation) · [Expo](#expo) · [Godot](#godot) · [Compatibility](#compatibility) · [Validation status](#validation-status) · [Signing setup](#get-the-apple-signing-files-from-eas) · [Submit to Apple](#submit-to-apple) · [Documentation](#documentation)

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
| App Store | Upload tested with CS Callouts; Apple processing and approval remain unverified. Precompiled assets are still required. |
| Host systems | Linux x86_64 validated. Windows and macOS have not been validated. |

See [Validation](docs/validation.md) for evidence and test scope.

## Validation status

- **Unit tests (live CI):** the badge reports the latest push run on `main` of the [SDK-free test workflow](.github/workflows/tests.yml). It installs the Python package, runs the unit suite, and checks Python compilation on Linux. It does not build or sign an IPA. Until the workflow has run on `main`, there is no CI pass to claim.
- **Expo and Godot (documented manual tests):** minimal Expo SDK 54 and Godot 4.5.1 examples were built, signed, installed, and opened on an iPhone on October 15, 2026. These static badges link to [the recorded scope](docs/validation.md#device-tests); they do not automatically revalidate later commits or other apps.
- **Apple upload (documented manual test):** CS Callouts was uploaded with a Linux-built executable and `Assets.car` reused from an EAS build of the same app. [This evidence](docs/validation.md#apple-upload-example-cs-callouts) covers upload only; Apple processing, TestFlight, App Review, and publication remain unverified.

These indicators describe separate checks, not a percentage of completion or a guarantee of App Store readiness.

## Demo

[![Expo build and installation on a real iPhone](docs/assets/expo-build-install-poster.jpg)](docs/assets/expo-build-install-demo.mp4)

[Watch the continuous demonstration](docs/assets/expo-build-install-demo.mp4): local Expo build, signing verification, installation, and the app running on an iPhone. Recorded October 15, 2026; 3 min 41 sec, without pauses or cuts. Credential setup is explained; existing credentials are used. Audio was removed for sharing. The sample app interface is in Portuguese; CLI output is in English.

The [website source](docs/index.html) includes an embedded player, commands, compatibility notes, and documentation links.

## Installation

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

Use an existing compatible toolchain if you already have one. Otherwise, prepare the components below once, outside the repository and your app:

```sh
export TOOLCHAIN="$HOME/.local/share/ios-linux/toolchain"
mkdir -p "$TOOLCHAIN"
```

The paths are part of the current CLI contract; merely installing tools on PATH does not satisfy every check. Follow the complete [expected layout and tested versions](docs/toolchain.md#expected-layout).

**Common compilation and signing tools**

- Obtain a compatible Linux Swift/Clang toolchain from [Swift's official distribution](https://www.swift.org/install/linux/) and place its contents under `$TOOLCHAIN/swift`, with `usr/bin/clang` and `usr/bin/swiftc`. The recorded build environment used Swift 6.4; a generic Linux Swift installation alone does **not** provide all Apple cross-compilation resources.
- Download `toolset-x86_64.tar.gz` from the upstream [darwin-tools-linux-llvm v1.1.0 release](https://github.com/xtool-org/darwin-tools-linux-llvm/releases/tag/v1.1.0). Extract and arrange it so the linker is `$TOOLCHAIN/darwin-tools/bin/ld64.lld`; inspect the archive layout before extracting into an existing toolchain.
- Supply Apple SDKs that you are authorized to obtain and use, starting from [Apple's Xcode resources](https://developer.apple.com/xcode/resources/). The current backend expects `sdks/iPhoneOS18.5.sdk` for Godot and `sdks/iPhoneOS26.4.sdk` plus `sdks/iPhoneOS26.5.sdk` for Expo. The package does not download or license them. SDK versions and stubs are not interchangeable; see the [compatibility notes](docs/toolchain.md#components-in-the-validated-environment).
- Install the external signer using npm:

```sh
npm install --prefix "$TOOLCHAIN/signing" --save-exact zsign-wasm@0.0.4
```

Keep your certificate, password, and provisioning profile outside the repository and toolchain; supply them later through [the credentials file](credentials.example.json). Installing the signer does not create Apple credentials.

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

Replace the source path with the `stdlib/public/Cxx` directory from the official [Swift 6.2 release sources](https://github.com/swiftlang/swift/tree/swift-6.2-RELEASE). Rebuild the overlay when changing Swift. See [runtime preparation](docs/toolchain.md#runtime-objects) for details.

**These Expo macro, Ruby-layout, and Darwin-overlay preparation steps are not automated by this repository.** The toolchain guide records their required inputs and layout, but is not yet a fully tested fresh-machine bootstrap recipe. Do not treat the commands above as a complete one-command toolchain installer.

**Godot-specific preparation**

Download the standard Linux x86_64 editor and matching export templates from the official [Godot 4.5.1 archive](https://godotengine.org/download/archive/4.5.1-stable/). Extract the editor and iOS templates, then place:

- The Linux editor executable at `$TOOLCHAIN/godot/godot`.
- The release **arm64 device** engine library at `$TOOLCHAIN/godot/libgodot.a`.
- Its matching MoltenVK library at `$TOOLCHAIN/godot/libMoltenVK.a`.

Use the device slices, not simulator slices, and keep the editor/template versions equal. See [Godot toolchain setup](docs/toolchain.md#godot). Ruby/CocoaPods and Expo macros are not needed for the Godot backend.

**Optional: install onto a physical iPhone**

Install libimobiledevice's `ideviceinstaller` using your distribution's packages; on Ubuntu, `sudo apt-get install ideviceinstaller`. Set `installer` in the config if using a different executable path. This is needed for `ios-anywhere install`, not merely to produce an IPA. Device pairing and a matching provisioning profile are still required.

### 3. Configure paths and check the selected backend

Create a config without overwriting an existing one:

```sh
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/ios-linux"
mkdir -p "$CONFIG_DIR"
if [ ! -e "$CONFIG_DIR/config.json" ]; then
  cp config.example.json "$CONFIG_DIR/config.json"
fi
```

Edit `$CONFIG_DIR/config.json` (normally `~/.config/ios-linux/config.json`) to point `toolchain` at your prepared directory, and adjust `llvm_ar`/`installer` if needed. `TOOLCHAIN` above is a shell variable for setup commands; the CLI reads its toolchain path from this JSON file.

Run the check for the backend you prepared:

```sh
ios-anywhere --engine expo doctor
# Or, for Godot:
ios-anywhere --engine godot doctor
```

`doctor` checks required paths and commands; it does not install missing tools, download SDKs, or prove a successful build. Use `--config /path/to/config.json` to select another configuration. Activate the virtual environment or use `.venv/bin/ios-anywhere` directly.

**Validation scope:** a fresh checkout and virtual environment on an existing Debian 13.6 x86_64 host passed CLI installation and all 13 unit tests on October 16, 2026; that host already had Python, Node/npm, and OpenSSL. This did not install the external toolchain or build an IPA. The Ubuntu package examples and full toolchain bootstrap above have not been validated end to end on a blank machine. See [device/build validation](docs/validation.md) for the separately tested prepared environment.

If you already have an App Store IPA and only want to upload it, skip local compiler/toolchain setup and follow [Submit to Apple](#submit-to-apple).

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

### Get the Apple signing files from EAS

The certificate used by an Expo app is an **Apple distribution certificate**. For this CLI you need its `.p12` file (including the private key), its password, and the matching `.mobileprovision` file. A push-notification key or App Store Connect API key is not a replacement for these signing files. Creating credentials requires the appropriate Apple Developer Program membership and team permissions; EAS can manage them for you. See [Expo's managed credentials guide](https://docs.expo.dev/app-signing/managed-credentials/).

For credentials already managed by EAS:

1. In your own app's EAS-configured project directory, sign in and open the iOS credentials manager:

   ```sh
   npx eas-cli login
   npx eas-cli credentials --platform ios
   ```

2. Select the intended build profile and app identity. Choose the credentials JSON upload/download option, then **download from EAS to the local credentials JSON**. Downloading existing files does not require generating or revoking a certificate. Follow [Expo's download instructions](https://docs.expo.dev/app-signing/syncing-credentials/); menu wording may vary with CLI version.
3. Keep the downloaded JSON, `.p12`, and provisioning profile private. Move them outside your project/repository, preserving their relative layout or updating paths in the JSON. Do not overwrite an existing credentials file without checking it. This Linux signer reads the files directly; it does not require importing them into a macOS Keychain.
4. Check the JSON against [credentials.example.json](credentials.example.json): `ios.provisioningProfilePath`, `ios.distributionCertificate.path`, and `ios.distributionCertificate.password` must refer to your actual local files and certificate password. The example's `REPLACE_LOCALLY` is a placeholder, not a working password. Then supply the private JSON with `--credentials /private/credentials.json` when building.

Never commit or paste the real password, private key, certificate bundle, provisioning profile, or credentials JSON into issues, logs, or chats. Exclude downloaded credential paths from version control before downloading, even when you intend to move them afterward.

### Find and pair your iPhone on Linux

Install the USB utilities; for Ubuntu:

```sh
sudo apt-get install libimobiledevice-utils usbmuxd ideviceinstaller
```

Connect the iPhone over USB, unlock it, and accept **Trust This Computer** on the phone if prompted. List connected USB device IDs:

```sh
idevice_id -l
```

Copy the intended phone's UDID, especially if more than one device is listed. It is not the serial number, bundle ID, or App Store Connect app ID. Use that value locally:

```sh
UDID="YOUR_DEVICE_UDID"
idevicepair -u "$UDID" pair
idevicepair -u "$UDID" validate
```

Respond to any trust prompt on the unlocked phone and retry pairing if needed. If no device appears, check the cable, USB connection, and `usbmuxd` before continuing. Keep the UDID out of public screenshots and bug reports. These commands follow the upstream [idevice_id](https://github.com/libimobiledevice/libimobiledevice/blob/master/docs/idevice_id.1) and [idevicepair](https://github.com/libimobiledevice/libimobiledevice/blob/master/docs/idevicepair.1) manuals.

### Include the phone in an Ad Hoc profile

Direct installation requires an appropriate device profile. An **App Store** profile is for App Store Connect/TestFlight distribution and cannot substitute for an **Ad Hoc** profile containing your iPhone's UDID.

In the app's EAS project, merge a dedicated profile into `eas.json` without replacing existing settings:

```json
{
  "build": {
    "preview": {
      "distribution": "internal"
    }
  }
}
```

Register the phone and inspect the registered-device list:

```sh
npx eas-cli device:create
npx eas-cli device:list
```

Follow the registration prompts for your Apple team and intended device. Registration with Expo alone does not update an already downloaded Apple provisioning profile. Only devices included in the profile used to sign the IPA can install it. See [Expo's internal-distribution guidance](https://docs.expo.dev/build/internal-distribution/).

If signing credentials do not exist yet, or you need to configure the `preview` profile, EAS provides a credentials-only command:

```sh
npx eas-cli credentials:configure-build --platform ios --profile preview
```

This can create or change credentials on Apple/EAS; review its prompts carefully, reuse a suitable existing certificate, and avoid revoking credentials used by other apps. It sets up credentials without starting a cloud build. See the [EAS CLI reference](https://docs.expo.dev/eas/cli/#eas-credentialsconfigure-build) and [credentials setup guidance](https://docs.expo.dev/eas/workflows/pre-packaged-jobs/).

Ensure the resulting Ad Hoc profile includes the phone. If an existing profile still lacks it, regenerate the profile with that device selected; Apple's [Ad Hoc profile instructions](https://developer.apple.com/help/account/provisioning-profiles/create-an-ad-hoc-provisioning-profile) explain choosing the matching App ID, distribution certificate, and registered devices, then generating and downloading it. Registration alone does not modify an old profile or IPA. Download the updated credentials/profile, then rebuild locally with a new output filename.

After building, check the intended device against the embedded profile and install:

```sh
IOS_LINUX_UDID="$UDID" ios-anywhere verify /path/to/MyApp-01.ipa
ios-anywhere install /path/to/MyApp-01.ipa --udid "$UDID"
```

A matching UDID is only one requirement; certificate validity, app identity, entitlements, and device compatibility still matter. Follow Apple's [device installation guidance](https://developer.apple.com/documentation/xcode/distributing-your-app-to-registered-devices) if Developer Mode is required. The account, download, registration, and USB steps here are instructions for you to perform; they were not exercised as part of the SDK-free unit tests.

### Verify and install an existing IPA

```sh
ios-anywhere verify /path/to/MyApp-01.ipa
ios-anywhere install /path/to/MyApp-01.ipa --udid YOUR_UDID
```

`verify` checks code and resource hashes, the CMS signature, and profile correspondence. It does not check Apple's trust or revocation status, establish App Store compatibility, or prove runtime behavior. `IOS_LINUX_UDID` can restrict verification to the intended device.

`build` writes the final IPA only after signing and verification. Existing output files are rejected. Installation is separate. `bundle` prepares resources without signing. Global options (`--project`, `--credentials`, `--engine`, `--config`) precede the subcommand.

## Submit to Apple

**Upload has been tested:** the CS Callouts experiment sent an IPA with a Linux-built executable to Apple, using an asset catalog reused from an EAS build of the same app. See the [documented upload result](docs/validation.md#apple-upload-example-cs-callouts). Apple processing, TestFlight availability, App Review, and publication have not been verified by that result.

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

Install the package first (`python3 -m pip install .`) and ensure Node.js is on PATH; the Expo module-resolution test invokes Node. Then run the same SDK-free checks as CI:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q ios_linux tests
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
- [AI agent guide](llm.txt)

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md) for responsible-use guidance covering all ios-anywhere versions, platforms, and distribution channels. Each copy retains its applicable licenses.

The project is intended for development, research, education, interoperability, and preservation of software you own or are authorized to use, modify, and distribute. Signing requires valid credentials; the CLI grants no distribution rights or App Store approval.

## Contributing

Contributions are welcome! [Open an issue](https://github.com/rodriguesabner/ios-anywhere/issues) to report a bug or suggest a feature, or [send a pull request](https://github.com/rodriguesabner/ios-anywhere/pulls) to improve the code or docs.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and checks, [Validation](docs/validation.md) for test scope, and [Architecture](docs/architecture.md) for project structure.

## License

Project-authored code is licensed under [MIT](LICENSE). Third-party material retains its own licenses and copyright notices; see [Third-party components](THIRD_PARTY.md).

**You must legally obtain and be authorized to use external tools and SDKs**, including Apple SDKs and toolchain dependencies, under their applicable terms. ios-anywhere grants no tool license, key, or activation entitlement. Unauthorized copies, stolen keys, unauthorized credential sharing, and bypassing license restrictions are not authorized by the project. This guidance does not amend MIT or third-party licenses.
