# Submit to Apple

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

**Upload has been tested:** the CS Callouts experiment sent an IPA with a Linux-built executable to Apple, using an asset catalog reused from an EAS build of the same app. See the [documented upload result](validation.md#apple-upload-example-cs-callouts). Apple processing, TestFlight availability, App Review, and publication have not been verified by that result.

Sources: [EAS Submit for iOS](https://docs.expo.dev/submit/ios/), [submitting an existing IPA](https://docs.expo.dev/deploy/submit-to-app-stores/).
