# Signing and device setup

[Back to quick commands](../README.md#signing-setup-and-device-preparation)

Use the format in [credentials.example.json](../credentials.example.json). Certificate and profile paths can be absolute or relative to the credentials file. For direct device installation, the profile must match the app identity and include the device. Supply existing credentials, or use the guided signing assistant below.

### Guided signing and saved devices

Run `ios-anywhere` and choose **Set up signing**, or:

```sh
ios-anywhere --config ~/.config/ios-anywhere/expo.json \
  signing-setup --output ~/private-signing/my-app
```

Select the config for either installed engine. This command needs Node, npm, and OpenSSL; it does not build an app. On first use it asks to install `@expo/apple-utils@2.2.1` and `prompts@2.4.2` outside the repository. Apple login, two-factor authentication, and team selection are handled by that unofficial library, which may cache your Apple session locally.

1. Enter your explicit bundle ID and select an existing distribution certificate.
2. Provide the matching `.p12` and its password. The assistant verifies the certificate and private key locally before proceeding. It cannot recover a missing private key or generate a new certificate.
3. Select a registered device or enter a new device name and UDID.
4. Confirm the displayed team, bundle ID, certificate, device, and output folder. Only then can it register a device, create a missing App ID, and create a new Ad Hoc profile. Device registration counts toward Apple's limits.
5. Use the generated `credentials.json` when building with that same bundle ID.

Existing output folders are rejected. The new folder is private (`0700`); its files use `0600`. The JSON contains your P12 password, so keep the entire folder out of version control. Cancelling the final confirmation creates no Apple resources. If a later operation fails, partial local files and already-created Apple resources are preserved, never revoked automatically. Review them before retrying with a new folder.

This flow covers **one app and one device**, without configuring capabilities. Apps with extensions or special entitlements still need matching profiles for each target; do not replace an existing multi-target credentials file with this single-target result.

Successful setup saves the phone's name and UDID in `$XDG_CONFIG_HOME/ios-anywhere/devices/saved.json` (default `~/.config/ios-anywhere/devices/saved.json`). **Install an IPA on iPhone** lets you select it or enter and save another phone. Saving a phone locally does not register it with Apple or modify an IPA. Installation checks every embedded app/extension profile for the selected UDID before invoking the installer. Connect, unlock, and trust/pair the phone as described below. Explicit `install --udid` commands still work and do not save a device automatically.

The device check does not verify Apple's trust/revocation status or replace `verify`. Creating another profile does not update an existing IPA: rebuild it with the new credentials.

### Godot: create a profile for your own bundle ID

A Godot directory is not an EAS project. Running `eas credentials` there, or in this CLI's repository, fails. You do not need an Expo app to create Apple credentials: use [Certificates, Identifiers & Profiles](https://developer.apple.com/account/resources/) with your Apple Developer team.

1. Register an explicit App ID such as `com.example.truck` under Identifiers.
2. Register the iPhone's UDID under Devices (obtain it with `idevice_id -l`).
3. Under Profiles, create an **Ad Hoc** profile, select that App ID, your Apple Distribution certificate, and your iPhone, then download it as `app.mobileprovision`.
4. Use the corresponding certificate **and its private key** in a `.p12`, plus its password. A downloaded `.cer` alone is insufficient. An existing EAS-managed distribution certificate can be downloaded from its Expo project's credentials manager and reused for another app in the same Apple team.

The bundle ID passed to `build` must match the profile exactly. Changing `--bundle-id` does not register a new app or update a profile. The shared test ID used during development is not required by ios-anywhere; use your own ID and profile. Reusing an installed app's ID updates/replaces that app.

#### Commands used during development

The original flow was a local Node script using `@expo/apple-utils` after Apple authentication through EAS. It restored the cached Apple session, selected an existing certificate and registered device, created the App ID if missing, and created an Ad Hoc profile. It did **not** create the certificate/private key or register the phone. The original invocation was `node provision-local.cjs`; that private script contained machine-specific paths and account identifiers.

A portable adaptation is now included at [examples/signing/create-adhoc-profile.cjs](../examples/signing/create-adhoc-profile.cjs). Unlike the original script's named-profile reuse, it creates a fresh profile containing the selected device on each run. It never revokes a certificate or overwrites an existing output file. **Running it creates resources in your Apple account.** It is an advanced example using an unofficial library, not a supported Apple CLI or an automatic login flow.

From the ios-anywhere repository root:

```sh
# Keep dependencies and credentials outside the repository.
mkdir -p "$HOME/.local/share/ios-anywhere/apple-profile-helper" "$HOME/private-signing/truck"
npm install --prefix "$HOME/.local/share/ios-anywhere/apple-profile-helper" --ignore-scripts @expo/apple-utils@2.2.1

export APPLE_ID="your-apple-account@example.com"
export APPLE_TEAM_ID="YOUR_TEAM_ID"
export APPLE_CERTIFICATE_ID="YOUR_EXISTING_DISTRIBUTION_CERTIFICATE_ID"
export DEVICE_UDID="YOUR_REGISTERED_IPHONE_UDID"
export BUNDLE_ID="com.example.truck"
export PROFILE_OUTPUT="$HOME/private-signing/truck/app.mobileprovision"

NODE_PATH="$HOME/.local/share/ios-anywhere/apple-profile-helper/node_modules" \
  node examples/signing/create-adhoc-profile.cjs
```

`APPLE_CERTIFICATE_ID` is the existing certificate's Apple resource ID, not its serial number or the `.p12` filename. The `.p12` must belong to that certificate. This helper requires a valid cached **Apple** session for that account/team; `npx eas-cli login` only logs in to Expo. If the session is unavailable, use the portal procedure above, or authenticate with Apple using `npx eas-cli credentials --platform ios` **inside an existing EAS-configured Expo project**. There is no need to create an Expo project just for Godot. Never share cached sessions.

Copy your corresponding `.p12` into the same private folder as `distribution.p12`, then create `credentials.json` there using this structure (replace the password locally):

```json
{
  "ios": {
    "provisioningProfilePath": "app.mobileprovision",
    "distributionCertificate": {
      "path": "distribution.p12",
      "password": "YOUR_P12_PASSWORD"
    }
  }
}
```

```sh
chmod 600 "$HOME/private-signing/truck/"*
ios-anywhere --engine godot \
  --project "$HOME/truck_town" \
  --bundle-id "$BUNDLE_ID" \
  --credentials "$HOME/private-signing/truck/credentials.json" \
  build --output "$HOME/truck_town/truck.ipa"
```

These commands explain the earlier hidden preparation step. The portable adaptation has local checks; it has not been used to create a new profile as part of this documentation update.

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
4. Check the JSON against [credentials.example.json](../credentials.example.json): `ios.provisioningProfilePath`, `ios.distributionCertificate.path`, and `ios.distributionCertificate.password` must refer to your actual local files and certificate password. The example's `REPLACE_LOCALLY` is a placeholder, not a working password. Then supply the private JSON with `--credentials /private/credentials.json` when building.

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

