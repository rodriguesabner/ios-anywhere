<div align="center">

# ios-anywhere

### From your project to your iPhone. Built locally on Linux.

**Expo · Godot · Compile · Sign · Install**

![Status: experimental](https://img.shields.io/badge/status-experimental-f0b429)
![Host: Linux x86_64](https://img.shields.io/badge/host-Linux_x86__64-20252b)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)

[![Unit tests (live CI on main)](https://github.com/rodriguesabner/ios-anywhere/actions/workflows/tests.yml/badge.svg?branch=main&event=push)](https://github.com/rodriguesabner/ios-anywhere/actions/workflows/tests.yml?query=branch%3Amain)
[Website](https://rodriguesabner.github.io/ios-anywhere/) · [Get started](#installation) · [Demo](#demo) · [Documentation](#documentation)

</div>

Build, sign, and install iOS apps locally on Linux. Supports **Godot** and **Expo**, with valid Apple signing credentials. No Mac or EAS Build is needed to run the local build workflow.

**Experimental:** start with Godot 4.5.1 / GDScript for the guided setup. Expo has an experimental setup for Ubuntu 24.04. Linux x86_64 is the tested host platform; not every project is supported.

<a id="installation"></a>

## 1. Install the CLI

On Ubuntu 24.04 / Linux x86_64:

```sh
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip openssl curl unzip

git clone https://github.com/rodriguesabner/ios-anywhere.git
cd ios-anywhere
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
```

Use Python 3.11.8+ or 3.12+. In a new terminal, activate this virtual environment again before using the CLI.

### Open the interactive CLI

```sh
ios-anywhere
```

```text
? What do you want to do?
  Get started — guided setup, build and install
  Build an IPA
  Install on iPhone
  Manage signing & devices
  Advanced
  Exit
```

**First time? Choose Get started.** The guide walks through engine → existing tools or setup → tools check → project → existing credentials or Apple signing setup → build → optional installation. Review and change your project, credentials or output before building. The default output is `<project>/iosapp.ipa`.

Use **↑ / ↓** to select, **Enter** to continue, and **Ctrl+C** to cancel. File and folder prompts offer path completion. Choices stay available during retries in the current guided session; they are not saved across restarts. Saved iPhones are reused across sessions. A failed installation can be retried without rebuilding.

| Choose | What happens next |
| --- | --- |
| **Get started** | Follow the guided workflow, reusing existing tools and credentials where available. |
| **Build an IPA** | Choose engine, config, project, signing JSON and output. |
| **Install on iPhone** | Choose an IPA and a saved iPhone, or save another device. |
| **Manage signing & devices** | Create Apple signing credentials, or choose/save an iPhone. |
| **Advanced** | Set up build tools, check tools (doctor), verify an IPA, or export resources only. |

**Which configuration?** A config locates your installed tools; it is not your Apple credentials. The selector shows its name, toolchain folder and config path. Use `expo.json` for Expo and `godot.json` for Godot; older `config.json` installations keep their original name. The guided flow checks the selected tools before building.

**Bundle ID:** the guided review displays the Expo `ios.bundleIdentifier` and checks it against the supplied provisioning profiles. Builds also perform this check before preparing native sources. Missing or mismatched identifiers stop with instructions to fix the Expo configuration or select matching credentials. Dynamic `app.config.js` / `app.config.ts` configurations are resolved with the project's installed Expo CLI; run `npm ci` in the project first if dependencies are missing. This identity check does not replace final signature verification.

**Which signing folder?** Choose a new private folder outside your project, such as `~/private-signing/my-app`. The signing assistant saves the certificate, profile and `credentials.json` there. If you already have these files, select **Use an existing credentials.json** instead. The first signing setup asks to download npm helpers that communicate with Apple; this does not start an EAS build. Apple resource creation requires a separate confirmation.

The five steps below show the same workflow with explicit commands.

## 2. Set up your build tools

**Godot:** have at least **8 GiB free**, then run:

```sh
ios-anywhere --config "$HOME/.config/ios-anywhere/godot.json" setup \
  --engine godot --toolchain "$HOME/.local/share/ios-anywhere/godot-toolchain"
ios-anywhere --config "$HOME/.config/ios-anywhere/godot.json" --engine godot doctor
```

Follow the prompts to install the compiler, linker, Godot libraries, signer, and iPhone USB utilities. Choose your local iPhoneOS 18.5 SDK or the unofficial SDK mirror. The mirror is not Apple-authenticated; Apple SDK terms still apply. [Setup details and troubleshooting →](docs/setup.md)

**Expo (Ubuntu 24.04 x86_64):** have at least **20 GiB free**, then run:

```sh
ios-anywhere --config "$HOME/.config/ios-anywhere/expo.json" setup \
  --engine expo --toolchain "$HOME/.local/share/ios-anywhere/expo-toolchain"
ios-anywhere --config "$HOME/.config/ios-anywhere/expo.json" --engine expo doctor
```

This installs Swift, Node, CocoaPods, macros, SDKs, and compatibility objects. It is **experimental**: Expo Meatball Animation was built on another Linux PC and opened on an iPhone, but a fully clean-machine bootstrap has not been independently verified. These separate config/toolchain paths allow Expo and Godot to coexist. Existing installation paths are preserved; choose your saved config instead of rerunning setup over it. Other hosts can use the [manual guide](docs/installation.md#2-prepare-the-external-toolchain).

<a id="signing-setup-and-device-preparation"></a>

## 3. Prepare your signing credentials

Connect and unlock your iPhone, accept **Trust This Computer**, and get its UDID:

```sh
idevice_id -l
```

Choose **Manage signing & devices → Create Apple signing credentials** in the menu, or run:

```sh
ios-anywhere --config "$HOME/.config/ios-anywhere/expo.json" \
  signing-setup --output "$HOME/private-signing/my-app"
```

Use your Godot config instead for a Godot toolchain. Sign in to Apple, select your team, enter your app's **bundle ID**, select an existing distribution certificate, and provide its **`.p12` with private key and password**. Choose a registered iPhone or enter a new name and UDID. Review and confirm the Apple resources to create.

The assistant generates an **Ad Hoc profile** and `credentials.json` in a new private folder, and saves the iPhone locally for later installation. It never creates or revokes certificates. You need Apple Developer membership and appropriate team permissions. The helper uses the unofficial `@expo/apple-utils` library and installs its npm dependencies on first use after confirmation. For apps with extensions, configure each target separately; this assistant prepares one app and one device.

Keep these three files together in a private folder outside the repository:

```text
$HOME/private-signing/my-app/
├── credentials.json
├── distribution.p12
└── app.mobileprovision
```

The signing assistant writes this JSON for you. For existing files, follow the [credentials format and manual setup](docs/signing.md). Keep passwords, certificates and profiles outside your repository.

**Prefer manual setup?** Follow the [Apple portal steps or provisioning script](docs/signing.md#godot-create-a-profile-for-your-own-bundle-id). Build-tool `setup` and Apple `signing-setup` are separate steps.

**Already have EAS credentials?** Run `npx eas-cli credentials --platform ios` inside your EAS-configured **Expo project**, then download the credentials. It does not work inside a Godot project or this CLI repository. [Full signing guide →](docs/signing.md)

## 4. Build your IPA

Choose your engine and replace the example paths. Use a new output filename for each build.

<a id="godot"></a>

**Godot** — the project folder must contain `project.godot`:

```sh
ios-anywhere --config "$HOME/.config/ios-anywhere/godot.json" --engine godot \
  --project "$HOME/my-game" \
  --bundle-id com.example.mygame \
  --credentials "$HOME/private-signing/my-app/credentials.json" \
  build --output "$HOME/my-game/iosapp.ipa"
```

Replace `com.example.mygame` with the **exact bundle ID authorized by your profile**. Use Godot 4.5.1 / GDScript without C# or GDExtensions.

<a id="expo"></a>

**Expo** — the project needs `package.json`, `package-lock.json`, and `ios.bundleIdentifier` in its Expo configuration:

```sh
ios-anywhere --config "$HOME/.config/ios-anywhere/expo.json" --engine expo \
  --project "$HOME/my-app" \
  --credentials "$HOME/private-signing/my-app/credentials.json" \
  build --output "$HOME/my-app/iosapp.ipa"
```

For Expo, merge the matching ID into your existing `app.json` (do not replace the rest of the file):

```json
{
  "expo": {
    "ios": {
      "bundleIdentifier": "com.example.myapp"
    }
  }
}
```

Use the ID authorized by your provisioning profile. If you have `app.config.js` or `app.config.ts`, ensure the resolved configuration uses that ID. A mismatch stops verification with `Profile identity differs from app`.

The menu suggests `<project>/iosapp.ipa`. Existing IPA files are never overwritten: choose a new filename for another build.

The CLI builds an isolated copy and publishes the IPA only after signing and verification. Build trusted projects: their scripts and dependencies execute locally.

## 5. Install on your iPhone

In the menu, choose **Install an IPA on iPhone**, select the IPA, then choose your saved device by name. The CLI checks that its UDID is included in every embedded app/extension profile. Keep the iPhone connected, unlocked and paired.

For an explicit command, replace the UDID and IPA path below. For Godot, use your game folder and `godot.json` instead of `expo.json`:

```sh
UDID="YOUR_IPHONE_UDID"
IPA="$HOME/my-app/iosapp.ipa"
idevicepair -u "$UDID" pair

IOS_LINUX_UDID="$UDID" ios-anywhere verify "$IPA"
ios-anywhere --config "$HOME/.config/ios-anywhere/expo.json" install "$IPA" --udid "$UDID"
```

Open the app on your iPhone. Installing with the same bundle ID updates the existing app.

**Have fun!** 🎉

## CLI reference

```sh
ios-anywhere --help
ios-anywhere setup --help
ios-anywhere signing-setup --help
ios-anywhere build --help
ios-anywhere install --help
```

Global options go **before** the command: `--config`, `--engine`, `--project`, `--credentials`, and Godot's `--bundle-id`. Command-specific options such as `build --output` and `install --udid` go after it. `verify` does not require a toolchain config.

To export resources only, use the same config/engine/project options as your build and replace `build --output ...` with `bundle`; signing credentials are not needed.

### Update the CLI

From your existing clone, with its virtual environment activated:

```sh
git pull --ff-only
python -m pip install .
```

A Git update alone does not update a non-editable Python installation. Keep your saved configs and toolchains; a CLI update does not normally require downloading them again.

### If a build fails

Open the log path printed for the failing step. Signing and verification details are in `sign.log` and `verify.log` inside that build's cache directory. Fix the reported cause and rerun with the same config and project. Keep the cache unless troubleshooting specifically requires removing it.

<a id="submit-to-apple"></a>

## Publish to the App Store

For an existing **App Store-signed IPA**, run this inside your EAS-configured Expo project:

```sh
npx eas-cli submit --platform ios --profile production --path /path/to/MyApp-AppStore.ipa
```

The Ad Hoc IPA from the steps above is for device testing. Store submission needs the appropriate profile, a unique build number, and compliant assets. [Submission configuration and requirements →](docs/submission.md)

## Demo

[![Expo build and installation on a real iPhone](docs/assets/expo-build-install-poster.jpg)](docs/assets/expo-build-install-demo.mp4)

[Watch the demo](docs/assets/expo-build-install-demo.mp4): local build, signing, installation, and an Expo app running on an iPhone.

## Reproduced projects

Built on Linux and tested on a real iPhone:

| Project | Engine | Result |
| --- | --- | --- |
| [Truck Town](https://github.com/godotengine/godot-demo-projects/tree/master/3d/truck_town) | Godot | Built on another PC; installed and running. |
| [Expo Meatball Animation](https://github.com/rit3zh/expo-meatball-animation) | Expo SDK 53 + Skia | Built on another PC; installed and initial UI rendered. |
| [Expo counter](examples/expo-counter) | Expo SDK 54 | Built, installed, and counter tested on an iPhone. |

<p>
  <img src="docs/assets/reproduced/godot-truck-town.png" alt="Truck Town running on an iPhone" width="540">
  <img src="docs/assets/reproduced/expo-meatball-open.png" alt="Expo Meatball Animation open on an iPhone" width="250">
</p>

[More screenshots, test dates, and scope →](docs/reproduced-projects.md)

<a id="validation-status"></a>

## Compatibility

| Engine / workflow | Status |
| --- | --- |
| Godot 4.5.1 / GDScript | Guided setup; Truck Town built on another PC and ran on an iPhone. |
| Expo SDK 53 + Skia | Meatball Animation built on another Linux PC, installed and opened on an iPhone. |
| Expo SDK 54 examples | Experimental Ubuntu 24.04 setup; examples built and tested on an iPhone. Native dependencies may need adaptation. |
| Widgets and extensions | Not supported by the generic CLI workflow. |
| App Store | Upload tested; Apple processing, review, and publication remain unverified. Precompiled asset catalogs are required. |

The initial Godot second-PC test required manually installing USB utilities, now included in setup. Later Expo testing confirmed installation and initial UI rendering after the documented compatibility fixes. These are project-specific results; CI checks code, not device execution. [Test evidence and limits →](docs/validation.md)

## Documentation

- [Setup and troubleshooting](docs/setup.md)
- [Signing credentials and profile creation](docs/signing.md)
- [Manual installation and limitations](docs/installation.md)
- [App Store submission](docs/submission.md)
- [Toolchain reference](docs/toolchain.md)
- [Architecture](docs/architecture.md)
- [Reproduced projects and screenshots](docs/reproduced-projects.md)
- [Validation](docs/validation.md)
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
