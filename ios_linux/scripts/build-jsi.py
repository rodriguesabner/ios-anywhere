"""Build Expo's Swift/C++ JSI framework using the project's resolved sources."""
from pathlib import Path
import json
import os
import plistlib
import subprocess
import sys


tools = Path(os.environ['IOS_LINUX_TOOLCHAIN'])
root = Path(os.environ['IOS_LINUX_BUILD'])
project = Path(os.environ['IOS_LINUX_PROJECT'])
pkg = project / 'node_modules/expo-modules-jsi/apple'
pods = project / 'ios/Pods'
out = root / 'products/ExpoModulesJSI'
sdk = tools / 'sdks' / (os.environ.get('IOS_LINUX_SDK') or 'iPhoneOS26.4.sdk')
sdk_version = json.loads((sdk / 'SDKSettings.json').read_text())['Version']
out.mkdir(parents=True, exist_ok=True)
subprocess.run(
    ['bash', str(pkg / 'scripts/generate-modulemap.sh')],
    env={**os.environ, 'PODS_ROOT': str(pods),
         'RN_ROOT': str(project / 'node_modules/react-native')},
    check=True,
)
cpp = pkg / 'Sources/ExpoModulesJSI-Cxx'
modulemap = out / 'cxx.modulemap'
modulemap.write_text(
    f'module ExpoModulesJSI_Cxx {{\n umbrella "{cpp / "include"}"\n export *\n}}\n'
)
includes = [
    tools / 'swift/usr/include', pods / 'Headers/Public',
    cpp / 'include', cpp / 'include/Public',
    project / 'node_modules/react-native/ReactCommon',
    project / 'node_modules/react-native/ReactCommon/jsi',
    pods / 'hermes-engine/destroot/include',
]
includes += sorted(p for p in (pods / 'Headers/Public').iterdir() if p.is_dir())
includes += [fw / 'Headers' for fw in pods.rglob('*.xcframework/ios-arm64/*.framework')]
base = [
    '-target', 'arm64-apple-ios16.4', '-sdk', str(sdk),
    '-resource-dir', str(tools / 'darwin-resource'),
    '-I', str(tools / 'darwin-resource/shims'),
    '-module-cache-path', str(root / 'module-cache'),
]
flags = [
    '-Xcc', '-std=c++20', '-cxx-interoperability-mode=default',
    '-Xcc', f'-fmodule-map-file={modulemap}',
    '-Xcc', f'-fmodule-map-file={pkg / ".generated/module.modulemap"}',
    '-Xcc', '-iapinotes-modules', '-Xcc', str(pkg / 'APINotes'),
]
for include in includes:
    flags += ['-Xcc', '-I' + str(include)]
sources = sorted(map(str, (pkg / 'Sources/ExpoModulesJSI').rglob('*.swift')))
assert sources and (pods / 'Headers/Public/React-jsi/jsi/jsi.h').exists()
# Modules are consumed by this exact compiler; rebuild together on toolchain changes.
cmd = [
    str(tools / 'swift/usr/bin/swiftc'), *base, *flags, '-swift-version', '6',
    '-enable-upcoming-feature', 'NonisolatedNonsendingByDefault',
    '-enable-upcoming-feature', 'InferIsolatedConformances',
    '-Xfrontend', '-clang-header-expose-decls=has-expose-attr',
    '-enable-library-evolution', '-enable-experimental-feature', 'AssumeResilientCxxTypes',
    '-parse-as-library', '-whole-module-optimization', '-O', '-assert-config', 'Release',
    '-module-name', 'ExpoModulesJSI', '-emit-module',
    '-emit-module-path', str(out / 'ExpoModulesJSI.swiftmodule'),
    '-emit-object', '-o', str(out / 'ExpoModulesJSI.o'), *sources,
]
(out / 'command.json').write_text(json.dumps(cmd, indent=2))
with (out / 'compile.log').open('w') as log:
    result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
print('ExpoModulesJSI Swift exit:', result.returncode, flush=True)
if result.returncode:
    sys.exit(result.returncode)

objects = [out / 'ExpoModulesJSI.o']
for source in sorted(cpp.glob('*.cpp')):
    obj = out / (source.stem + '.o')
    command = [
        str(tools / 'swift/usr/bin/clang++'), '-target', 'arm64-apple-ios16.4',
        '-isysroot', str(sdk), '-std=c++20', '-O1',
    ]
    for include in includes:
        command += ['-I', str(include)]
    subprocess.run([*command, '-c', str(source), '-o', str(obj)], check=True)
    objects.append(obj)

# Match Expo's dynamic framework: React/Hermes symbols resolve in the host process.
framework = out / 'ExpoModulesJSI.framework'
framework.mkdir(exist_ok=True)
link = [
    str(tools / 'darwin-tools/bin/ld64.lld'), '-dylib', '-arch', 'arm64',
    '-platform_version', 'ios', '16.4', sdk_version, '-syslibroot', str(sdk),
    '-L' + str(sdk / 'usr/lib/swift'), '-undefined', 'dynamic_lookup',
    '-install_name', '@rpath/ExpoModulesJSI.framework/ExpoModulesJSI',
    '-lSystem', '-lc++', '-o', str(framework / 'ExpoModulesJSI'), *map(str, objects),
]
(out / 'link-command.json').write_text(json.dumps(link, indent=2))
with (out / 'link.log').open('w') as log:
    subprocess.run(link, stdout=log, stderr=subprocess.STDOUT, check=True)
version = json.loads((pkg.parent / 'package.json').read_text())['version']
(framework / 'Info.plist').write_bytes(plistlib.dumps({
    'CFBundleExecutable': 'ExpoModulesJSI', 'CFBundleIdentifier': 'org.expo.ExpoModulesJSI',
    'CFBundlePackageType': 'FMWK', 'CFBundleVersion': version,
    'CFBundleShortVersionString': version, 'MinimumOSVersion': '16.4',
}))
print('ExpoModulesJSI linked', flush=True)
