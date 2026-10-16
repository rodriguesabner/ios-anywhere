// Adapted from the script used for the first Godot device build.
const fs = require('node:fs');
const assert = require('node:assert/strict');

async function main() {
  const required = ['APPLE_ID', 'APPLE_TEAM_ID', 'APPLE_CERTIFICATE_ID', 'DEVICE_UDID', 'BUNDLE_ID', 'PROFILE_OUTPUT'];
  for (const name of required) assert(process.env[name]?.trim(), `Set ${name} first`);
  const { APPLE_ID, APPLE_TEAM_ID, APPLE_CERTIFICATE_ID, DEVICE_UDID, BUNDLE_ID, PROFILE_OUTPUT } = process.env;
  assert(!fs.existsSync(PROFILE_OUTPUT), 'Profile output already exists; choose a new path');
  assert(/^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$/.test(BUNDLE_ID), 'Invalid bundle ID');
  const apple = require('@expo/apple-utils');
  const session = await apple.Auth.tryRestoringAuthStateFromUserCredentialsAsync(
    { username: APPLE_ID, teamId: APPLE_TEAM_ID }, { autoResolveProvider: true }
  );
  assert(session, 'No cached Apple session. Authenticate with Apple through EAS credentials first, or use the Apple Developer portal. Expo login alone is not sufficient.');
  const ctx = session.context;
  assert.equal(ctx.teamId, APPLE_TEAM_ID, 'Unexpected Apple team');
  const cert = (await apple.Certificate.getAsync(ctx)).find(c => c.id === APPLE_CERTIFICATE_ID);
  assert(cert, 'Distribution certificate not found in this team');
  const device = (await apple.Device.getAllIOSProfileDevicesAsync(ctx))
    .find(d => d.attributes.udid === DEVICE_UDID && d.attributes.status === 'ENABLED');
  assert(device, 'Register and enable this iPhone in the Apple Developer portal first');
  let bundle = await apple.BundleId.findAsync(ctx, { identifier: BUNDLE_ID });
  if (!bundle) bundle = await apple.BundleId.createAsync(ctx, {
    identifier: BUNDLE_ID, name: BUNDLE_ID, platform: apple.BundleIdPlatform.IOS,
  });
  const profile = await apple.Profile.createAsync(ctx, {
    bundleId: bundle.id, certificates: [cert.id], devices: [device.id],
    name: `${BUNDLE_ID} AdHoc ${Date.now()}`, profileType: apple.ProfileType.IOS_APP_ADHOC,
  });
  assert(profile.attributes.profileContent, 'Apple returned no profile content');
  fs.writeFileSync(PROFILE_OUTPUT, Buffer.from(profile.attributes.profileContent, 'base64'), { mode: 0o600, flag: 'wx' });
  console.log(`Ad Hoc profile saved: ${PROFILE_OUTPUT}`);
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
