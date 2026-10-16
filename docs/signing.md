# Signing and device setup

[Back to quick commands](../README.md#signing-verification-and-installation)

Use the format in [credentials.example.json](../credentials.example.json). Certificate and profile paths can be absolute or relative to the credentials file. For direct device installation, the profile must match the app identity and include the device. Supply your certificate, password, and profile; the CLI does not sign in to Apple or create profiles automatically.

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

