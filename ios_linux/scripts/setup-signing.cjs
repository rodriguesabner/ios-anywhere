// Uses Apple's existing distribution certificate; never creates or revokes keys.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');
const { X509Certificate, createPrivateKey, createPublicKey } = require('node:crypto');
const assert = require('node:assert/strict');
const udidPattern = /^(?:[0-9a-f]{8}-[0-9a-f]{16}|[0-9a-f]{40})$/i;

function checkP12(file, password, certificate) {
  assert(!/[\r\n]/.test(password), 'P12 passwords containing newlines are not supported.');
  function extract(flags) {
    for (const legacy of [[], ['-legacy']]) {
      const result = spawnSync('openssl', ['pkcs12', ...legacy, '-in', file, '-passin', 'stdin', ...flags],
        { input: password + '\n', encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 });
      if (result.status === 0) return result.stdout;
    }
    throw new Error('Cannot read the P12. Check its path, password, and private key.');
  }
  const cert = new X509Certificate(extract(['-clcerts', '-nokeys']));
  const expected = new X509Certificate(Buffer.from(certificate, 'base64'));
  assert(cert.raw.equals(expected.raw), 'The P12 does not match the selected Apple certificate.');
  const key = createPrivateKey(extract(['-nocerts', '-nodes']));
  const publicKey = k => k.export({ type: 'spki', format: 'der' });
  assert(publicKey(createPublicKey(key)).equals(publicKey(cert.publicKey)), 'The P12 private key does not match its certificate.');
}

async function main(apple, prompts, output) {
  assert(!fs.existsSync(output), 'Choose a new output folder.');
  const ask = async (type, message, options = {}) => {
    const result = await prompts({ type, name: 'value', message, ...options },
      { onCancel: () => { throw new Error('Cancelled.'); } });
    assert(Object.hasOwn(result, 'value'), 'Cancelled.');
    return result.value;
  };
  console.log('Ad Hoc signing for one app and one iPhone. Have your existing distribution P12 and password ready.');
  console.log('Apple login/2FA and team selection follow. The authentication library may cache your Apple session locally.');
  const session = await apple.Auth.loginAsync();
  assert(session?.context?.teamId, 'Apple authentication did not return a team.');
  const ctx = session.context;
  const bundleID = (await ask('text', 'Bundle ID', {
    validate: v => /^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$/.test(v) || 'Enter an explicit bundle ID, such as com.example.game.',
  })).trim();
  assert(/^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$/.test(bundleID), 'Invalid bundle ID.');
  const certificates = (await apple.Certificate.getAsync(ctx)).filter(c =>
    ['IOS_DISTRIBUTION', 'DISTRIBUTION'].includes(c.attributes.certificateType)
    && c.attributes.status !== 'Revoked' && Date.parse(c.attributes.expirationDate) > Date.now());
  assert(certificates.length, 'No valid distribution certificate found. Obtain a certificate and its private key first.');
  const cert = await ask('select', 'Existing distribution certificate', {
    choices: certificates.map(c => ({ title: `${c.attributes.name} (${c.id}, expires ${c.attributes.expirationDate})`, value: c })),
  });
  let p12 = await ask('text', 'Existing .p12 path');
  p12 = path.resolve(p12.replace(/^~(?=\/|$)/, os.homedir()));
  assert(fs.statSync(p12).isFile(), 'P12 path must be a file.');
  const password = await ask('password', 'P12 password');
  checkP12(p12, password, cert.attributes.certificateContent);
  const allDevices = await apple.Device.getAllIOSProfileDevicesAsync(ctx);
  const selected = await ask('select', 'iPhone for this profile', {
    choices: [...allDevices.filter(d => d.attributes.status === 'ENABLED').map(d => ({
      title: `${d.attributes.name} (${d.attributes.udid})`, value: d,
    })), { title: 'Register another iPhone', value: 'new' }],
  });
  let device = selected === 'new' ? null : selected;
  let name = device?.attributes.name;
  let udid = device?.attributes.udid;
  if (!device) {
    name = (await ask('text', 'Device name', { validate: v => !!v.trim() || 'Enter a name.' })).trim();
    udid = (await ask('text', 'iPhone UDID (idevice_id -l)', {
      validate: v => udidPattern.test(v.trim()) || 'Enter a valid iPhone UDID.',
    })).trim().toUpperCase();
    assert(udidPattern.test(udid), 'Invalid UDID.');
    const existing = allDevices.find(d => d.attributes.udid.toUpperCase() === udid);
    assert(!existing, 'This device is already registered. Select it from the list, or manage its disabled status in Apple Developer.');
  }
  let bundle = await apple.BundleId.findAsync(ctx, { identifier: bundleID });
  console.log(`\nApple team: ${ctx.teamId}\nBundle ID: ${bundleID}\nCertificate: ${cert.id}\nDevice: ${name} (${udid})\nOutput: ${output}`);
  console.log(`${bundle ? 'Reuse' : 'Create'} App ID; ${device ? 'reuse' : 'register'} device; create a NEW Ad Hoc profile.`);
  if (!device) console.log('Device registration counts toward your Apple team device limit.');
  if (!await ask('confirm', 'Create these resources in your Apple account?', { initial: false })) return;
  fs.mkdirSync(path.dirname(output), { recursive: true, mode: 0o700 });
  fs.mkdirSync(output, { mode: 0o700 });
  const write = (name, data) => fs.writeFileSync(path.join(output, name), data, { flag: 'wx', mode: 0o600 });
  try {
    // Reserve private local files before creating resources; never roll back Apple resources by revoking them.
    write('distribution.p12', fs.readFileSync(p12));
    if (!device) device = await apple.Device.createAsync(ctx, { name, udid, platform: apple.BundleIdPlatform.IOS });
    if (!bundle) bundle = await apple.BundleId.createAsync(ctx, {
      identifier: bundleID, name: bundleID, platform: apple.BundleIdPlatform.IOS,
    });
    const profile = await apple.Profile.createAsync(ctx, {
      bundleId: bundle.id, certificates: [cert.id], devices: [device.id],
      name: `${bundleID} AdHoc ${Date.now()}`, profileType: apple.ProfileType.IOS_APP_ADHOC,
    });
    assert(profile.attributes.profileContent, 'Apple returned no profile content.');
    write('app.mobileprovision', Buffer.from(profile.attributes.profileContent, 'base64'));
    write('credentials.json', JSON.stringify({ ios: {
      provisioningProfilePath: 'app.mobileprovision', distributionCertificate: { path: 'distribution.p12', password },
    } }, null, 2) + '\n');
    write('device.json', JSON.stringify({ name, udid }) + '\n');
    console.log(`Signing credentials saved: ${path.join(output, 'credentials.json')}`);
    console.log('Keep this folder private: credentials.json contains the P12 password. Use the same bundle ID when building.');
  } catch (error) {
    console.error(`Setup stopped. Partial files remain in ${output}; any Apple resources already created are preserved.`);
    throw error;
  }
}

module.exports = { main, checkP12 };
if (require.main === module) {
  const { createRequire } = require('node:module');
  const helperRequire = createRequire(path.join(path.resolve(process.argv[2]), 'package.json'));
  main(helperRequire('@expo/apple-utils'), helperRequire('prompts'), path.resolve(process.argv[3]))
    .catch(error => { console.error(error.message); process.exitCode = 1; });
}
