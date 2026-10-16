from pathlib import Path
import subprocess, json, sys
import os
tools=Path(os.environ['IOS_LINUX_TOOLCHAIN'])
root=Path(os.environ['IOS_LINUX_BUILD'])
project=Path(os.environ['IOS_LINUX_PROJECT'])
pkg=project/'node_modules/expo-modules-jsi/apple'
pods=project/'ios/Pods'
out=root/'products/ExpoModulesJSI'
out.mkdir(parents=True,exist_ok=True)
subprocess.run(['bash',str(pkg/'scripts/generate-modulemap.sh')],env={**__import__('os').environ,'PODS_ROOT':str(pods),'RN_ROOT':str(project/'node_modules/react-native')},check=True)
cpp=pkg/'Sources/ExpoModulesJSI-Cxx'
modulemap=out/'cxx.modulemap'
modulemap.write_text(f'module ExpoModulesJSI_Cxx {{\n umbrella "{cpp / "include"}"\n export *\n}}\n')
includes=[tools/'swift/usr/include',pods/'Headers/Public',cpp/'include',cpp/'include/Public',project/'node_modules/react-native/ReactCommon',project/'node_modules/react-native/ReactCommon/jsi']
includes+=sorted(p for p in (pods/'Headers/Public').iterdir() if p.is_dir())
includes += [pods/'hermes-engine/destroot/include']
includes += [fw/'Headers' for fw in pods.rglob('*.xcframework/ios-arm64/*.framework')]
base=['-target','arm64-apple-ios16.4','-sdk',str(tools/'sdks/iPhoneOS26.4.sdk'),'-resource-dir',str(tools/'darwin-resource'),'-I',str(tools/'darwin-resource/shims'),'-module-cache-path',str(root/'module-cache')]
flags=['-Xcc','-std=c++20','-cxx-interoperability-mode=default','-Xcc',f'-fmodule-map-file={modulemap}','-Xcc',f'-fmodule-map-file={pkg/".generated/module.modulemap"}','-Xcc','-iapinotes-modules','-Xcc',str(pkg/'APINotes')]
for p in includes: flags+=['-Xcc','-I'+str(p)]
sources=sorted(map(str,(pkg/'Sources/ExpoModulesJSI').rglob('*.swift')))
assert sources and (pods/'Headers/Public/React-jsi/jsi/jsi.h').exists()
# shortcut: modules are consumed by this exact compiler; rebuild together after a toolchain change.
# Build the dependency from source with Release assertions.
cmd=[str(tools/'swift/usr/bin/swiftc'),*base,*flags,'-swift-version','6','-enable-upcoming-feature','NonisolatedNonsendingByDefault','-enable-upcoming-feature','InferIsolatedConformances','-Xfrontend','-clang-header-expose-decls=has-expose-attr','-enable-library-evolution','-enable-experimental-feature','AssumeResilientCxxTypes','-parse-as-library','-whole-module-optimization','-O','-assert-config','Release','-module-name','ExpoModulesJSI','-emit-module','-emit-module-path',str(out/'ExpoModulesJSI.swiftmodule'),'-emit-object','-o',str(out/'ExpoModulesJSI.o'),*sources]
(out/'command.json').write_text(json.dumps(cmd,indent=2))
with (out/'compile.log').open('w') as log:
 result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
print('ExpoModulesJSI Swift exit:',result.returncode,flush=True)
if result.returncode: sys.exit(result.returncode)
# Match Expo's dynamic framework: React and Hermes symbols resolve in the host app.
objects=[out/'ExpoModulesJSI.o']
for source in cpp.glob('*.cpp'):
 obj=out/(source.stem+'.o')
 compile_cmd=[str(tools/'swift/usr/bin/clang++'),'-target','arm64-apple-ios16.4','-isysroot',str(tools/'sdks/iPhoneOS26.4.sdk'),'-std=c++20','-O1']
 for include in includes: compile_cmd+=['-I',str(include)]
 subprocess.run([*compile_cmd,'-c',str(source),'-o',str(obj)],check=True)
 objects.append(obj)
fw=out/'ExpoModulesJSI.framework';fw.mkdir(exist_ok=True)
link=[str(tools/'darwin-tools/bin/ld64.lld'),'-dylib','-arch','arm64','-platform_version','ios','16.4','26.4','-syslibroot',str(tools/'sdks/iPhoneOS26.4.sdk'),'-L'+str(tools/'sdks/iPhoneOS26.4.sdk/usr/lib/swift'),'-undefined','dynamic_lookup','-install_name','@rpath/ExpoModulesJSI.framework/ExpoModulesJSI','-lSystem','-lc++','-o',str(fw/'ExpoModulesJSI'),*map(str,objects)]
with (out/'link.log').open('w') as log: subprocess.run(link,stdout=log,stderr=subprocess.STDOUT,check=True)
import plistlib
(fw/'Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable':'ExpoModulesJSI','CFBundleIdentifier':'org.expo.ExpoModulesJSI','CFBundlePackageType':'FMWK','CFBundleVersion':json.loads((pkg.parent/'package.json').read_text())['version'],'CFBundleShortVersionString':json.loads((pkg.parent/'package.json').read_text())['version'],'MinimumOSVersion':'16.4'}))
print('ExpoModulesJSI linked',flush=True)
