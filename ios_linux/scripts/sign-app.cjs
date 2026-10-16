const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { ZsignWasmClient } = require(process.env.IOS_LINUX_SIGNING_MODULE);
const root = __dirname;
const credentialFile = process.env.IOS_LINUX_CREDENTIALS;
const project = path.dirname(credentialFile);
const app = process.env.IOS_LINUX_APP;
let credentials = JSON.parse(fs.readFileSync(credentialFile)).ios;
assert(credentials, 'Missing iOS credentials');
if (credentials.distributionCertificate) credentials = { main: credentials };
const entries = Object.values(credentials);
assert(
  entries.length && entries.every((e) => e.distributionCertificate && e.provisioningProfilePath),
  'Invalid iOS credentials',
);
async function main() {
  assert(fs.existsSync(path.join(app, 'Info.plist')), 'No staged app');
  const client = await ZsignWasmClient.create();
  client.setLogLevel(0);
  const vfs = client.mod.FS;
  function upload(local, virtual) {
    vfs.mkdirTree(virtual);
    for (const name of fs.readdirSync(local)) {
      const src = path.join(local, name);
      const dst = `${virtual}/${name}`;
      if (fs.statSync(src).isDirectory()) upload(src, dst);
      else vfs.writeFile(dst, fs.readFileSync(src));
    }
  }
  upload(app, '/app/Bundle.app');
  vfs.mkdirTree('/sign');
  const cert = entries[0].distributionCertificate;
  vfs.writeFile('/sign/key.p12', fs.readFileSync(path.resolve(project, cert.path)));
  const provFiles = [];
  for (const [index, name] of Object.keys(credentials).entries()) {
    const dst = `/sign/profile-${index}.mobileprovision`;
    vfs.writeFile(
      dst,
      fs.readFileSync(path.resolve(project, credentials[name].provisioningProfilePath)),
    );
    provFiles.push(dst);
  }
  const result = client.signBundleMulti('/app/Bundle.app', {
    pkeyFile: '/sign/key.p12',
    password: cert.password,
    provFiles,
    forceSign: true,
  });
  assert(result === undefined || result === 0, `Signing failed: ${result}`);
  function download(virtual, local) {
    fs.mkdirSync(local, { recursive: true });
    for (const name of vfs.readdir(virtual).filter((x) => x !== '.' && x !== '..')) {
      const src = `${virtual}/${name}`;
      const dst = path.join(local, name);
      if (vfs.isDir(vfs.stat(src).mode)) download(src, dst);
      else fs.writeFileSync(dst, vfs.readFile(src));
    }
  }
  download('/app/Bundle.app', app);
  console.log('Signed app with supplied provisioning profiles.');
}
main().catch((error) => {
  let message = String(error.message);
  for (const entry of Object.values(credentials))
    if (entry.distributionCertificate?.password)
      message = message.split(entry.distributionCertificate.password).join('[REDACTED]');
  console.error(message);
  process.exitCode = 1;
});
