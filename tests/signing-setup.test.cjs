const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { X509Certificate } = require('node:crypto');
const { main, checkP12 } = require('../ios_linux/scripts/setup-signing.cjs');

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'ios-signing-test-'));
process.on('exit', () => fs.rmSync(temp, { recursive: true, force: true }));
const key = path.join(temp, 'key.pem');
const pem = path.join(temp, 'cert.pem');
const p12 = path.join(temp, 'cert.p12');
execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', key,
  '-out', pem, '-days', '1', '-subj', '/CN=Local unit test'], { stdio: 'ignore' });
execFileSync('openssl', ['pkcs12', '-export', '-inkey', key, '-in', pem, '-out', p12,
  '-passout', 'stdin'], { input: 'unit-test-password\n', stdio: ['pipe', 'ignore', 'ignore'] });
const certificateContent = new X509Certificate(fs.readFileSync(pem)).raw.toString('base64');
const udid = '00008000-0000000000000001';
const cert = { id: 'cert', attributes: { certificateType: 'DISTRIBUTION', status: 'Issued',
  expirationDate: '2099-01-01', name: 'Test', certificateContent } };
const device = { id: 'device', attributes: { name: 'Test phone', udid, status: 'ENABLED' } };

function appleFixture(existing) {
  const mutations = [];
  return { mutations,
    Auth: { loginAsync: async () => ({ context: { teamId: 'test-team' } }) },
    Certificate: { getAsync: async () => [cert] },
    Device: {
      getAllIOSProfileDevicesAsync: async () => existing ? [device] : [],
      createAsync: async (ctx, values) => { mutations.push(['device', values]); return device; },
    },
    BundleId: {
      findAsync: async () => existing ? { id: 'bundle' } : null,
      createAsync: async (ctx, values) => { mutations.push(['bundle', values]); return { id: 'bundle' }; },
    },
    Profile: { createAsync: async (ctx, values) => {
      mutations.push(['profile', values]);
      return { attributes: { profileContent: Buffer.from('mock-profile').toString('base64') } };
    } },
    BundleIdPlatform: { IOS: 'IOS' }, ProfileType: { IOS_APP_ADHOC: 'IOS_APP_ADHOC' },
  };
}
function answers(values) {
  return async () => { assert(values.length, 'Unexpected prompt'); return { value: values.shift() }; };
}

test('P12 certificate and password are validated', () => {
  checkP12(p12, 'unit-test-password', certificateContent);
  assert.throws(() => checkP12(p12, 'wrong-password', certificateContent), /Cannot read/);
  const other = path.join(temp, 'other.pem');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', path.join(temp, 'other.key'),
    '-out', other, '-days', '1', '-subj', '/CN=Another test'], { stdio: 'ignore' });
  assert.throws(() => checkP12(p12, 'unit-test-password',
    new X509Certificate(fs.readFileSync(other)).raw.toString('base64')), /does not match/);
});

test('declining confirmation creates no files or Apple resources', async () => {
  const apple = appleFixture(true), output = path.join(temp, 'cancelled');
  await main(apple, answers(['com.example.test', cert, p12, 'unit-test-password', device, false]), output);
  assert.deepEqual(apple.mutations, []);
  assert.equal(fs.existsSync(output), false);
});

test('existing identity and device are reused, private credentials are written', async () => {
  const apple = appleFixture(true), output = path.join(temp, 'existing');
  await main(apple, answers(['com.example.test', cert, p12, 'unit-test-password', device, true]), output);
  assert.deepEqual(apple.mutations.map(m => m[0]), ['profile']);
  assert.deepEqual(apple.mutations[0][1].devices, ['device']);
  assert.equal(fs.statSync(output).mode & 0o777, 0o700);
  for (const file of fs.readdirSync(output)) assert.equal(fs.statSync(path.join(output, file)).mode & 0o777, 0o600);
  const credentials = JSON.parse(fs.readFileSync(path.join(output, 'credentials.json')));
  assert.equal(credentials.ios.distributionCertificate.password, 'unit-test-password');
  await assert.rejects(main(apple, answers([]), output), /new output folder/);
});

test('new device and bundle are created only after confirmation', async () => {
  const apple = appleFixture(false), output = path.join(temp, 'new');
  await main(apple, answers(['com.example.test', cert, p12, 'unit-test-password', 'new', 'Test phone', udid, true]), output);
  assert.deepEqual(apple.mutations.map(m => m[0]), ['device', 'bundle', 'profile']);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(output, 'device.json'))), { name: 'Test phone', udid });
});

test('wrong P12 fails before Apple mutations', async () => {
  const apple = appleFixture(false);
  await assert.rejects(main(apple, answers(['com.example.test', cert, p12, 'wrong']), path.join(temp, 'bad')), /Cannot read/);
  assert.deepEqual(apple.mutations, []);
});

test('profile creation failure preserves files and prior Apple resources', async () => {
  const apple = appleFixture(false), output = path.join(temp, 'partial');
  apple.Profile.createAsync = async () => { throw new Error('API unavailable'); };
  await assert.rejects(main(apple, answers(['com.example.test', cert, p12, 'unit-test-password', 'new', 'Test phone', udid, true]), output), /API unavailable/);
  assert.deepEqual(apple.mutations.map(m => m[0]), ['device', 'bundle']);
  assert(fs.existsSync(path.join(output, 'distribution.p12')));
  assert(!fs.existsSync(path.join(output, 'credentials.json')));
});
