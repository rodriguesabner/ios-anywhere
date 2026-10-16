import json
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ios_linux import expo, signing
from ios_linux.config import Config


def target(name, kind='application', dependencies=(), resources=()):
    return dict(name=name, product_type='com.apple.product-type.' + kind,
                settings={'INFOPLIST_FILE':name + '/Info.plist',
                          'PRODUCT_BUNDLE_IDENTIFIER':'test.' + name},
                sources=[], headers=[], dependencies=list(dependencies), resources=list(resources))


class TargetsTests(unittest.TestCase):
    def test_plan_uses_product_type_not_order_or_api_restriction(self):
        main, widget = target('App'), target('Widget', 'app-extension')
        main['settings']['APPLICATION_EXTENSION_API_ONLY'] = 'YES'
        self.assertEqual(expo.target_plan([widget, main]), (main, [widget]))
        for apps in ([main, target('Other')], [widget], [target('Tests', 'bundle.unit-test')]):
            with self.assertRaises(ValueError): expo.target_plan(apps)

    def test_dependency_closure_excludes_other_target_and_rejects_cycles(self):
        libraries = [target('Pods-App', dependencies=['Shared','AppOnly']),
                     target('Pods-Widget', dependencies=['Shared','WidgetOnly']),
                     target('Shared'), target('AppOnly'), target('WidgetOnly')]
        self.assertEqual([t['name'] for t in expo.target_dependencies(libraries, target('Widget'))],
                         ['Shared', 'WidgetOnly', 'Pods-Widget'])
        libraries[2]['dependencies'] = ['Pods-Widget']
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            expo.target_dependencies(libraries, target('Widget'))
        with self.assertRaisesRegex(ValueError, 'Missing'):
            expo.target_dependencies([], target('App'))

    def test_staging_two_extensions_preserves_identity_and_scopes_resources(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            apps = [target('Widget', 'app-extension'), target('App'), target('Share', 'app-extension')]
            libraries = [target('Pods-App', dependencies=['ExpoWidgets']),
                         target('Pods-Widget', dependencies=['ExpoWidgets']), target('Pods-Share'), target('ExpoWidgets')]
            for app in apps:
                name = app['name']
                path = job / 'project/ios' / name
                path.mkdir(parents=True)
                info = {'CFBundleIdentifier':'$(PRODUCT_BUNDLE_IDENTIFIER)', 'CFBundleVersion':'7'}
                if name != 'App': info['NSExtension'] = {'NSExtensionPointIdentifier':'com.apple.widgetkit-extension'}
                (path/'Info.plist').write_bytes(plistlib.dumps(info))
                binary = job/'build/products'/name/name
                binary.parent.mkdir(parents=True)
                binary.write_bytes(name.encode())
            build = job/'build'
            (build/'app-graph.json').write_text(json.dumps(apps))
            (build/'pods-graph.json').write_text(json.dumps(libraries))
            resources = build/'app-resources'
            widget = resources/'ExpoWidgets.bundle'
            widget.mkdir(parents=True)
            (widget/'ExpoWidgets.bundle').write_bytes(b'widget javascript')
            (widget/'Info.plist').write_bytes(plistlib.dumps({'CFBundlePackageType':'BNDL'}))
            (resources/'main.jsbundle').write_bytes(b'app javascript')
            dest = expo.stage(job)
            self.assertTrue((dest/'main.jsbundle').is_file())
            for name in ('Widget','Share'):
                ext = dest/'PlugIns'/(name+'.appex')
                info = plistlib.loads((ext/'Info.plist').read_bytes())
                self.assertEqual(info['CFBundleIdentifier'], 'test.'+name)
                self.assertEqual(info['CFBundlePackageType'], 'XPC!')
                self.assertIn('NSExtension', info)
                self.assertNotIn('UIApplicationSceneManifest', info)
                self.assertNotIn('UILaunchScreen', info)
                self.assertFalse((ext/'main.jsbundle').exists())
                self.assertEqual((ext/name).read_bytes(), name.encode())
                self.assertEqual((ext/'ExpoWidgets.bundle/ExpoWidgets.bundle').exists(), name=='Widget')
            self.assertEqual(expo.stage(job), dest)  # Clean restaging.

    def test_link_uses_per_target_libraries_and_extension_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            apps = [target('App'), target('Widget','app-extension')]
            selected = [target('Pods-App', dependencies=['AppOnly']), target('AppOnly'),
                        target('Pods-Widget', dependencies=['WidgetOnly']), target('WidgetOnly')]
            for item in apps+selected:
                out = job/'build/products'/item['name']
                out.mkdir(parents=True)
                (out/'source.o').touch()
            for app in apps:
                name = 'Pods-'+app['name']
                support = job/'project/ios/Pods/Target Support Files'/name
                support.mkdir(parents=True)
                (support/(name+'.release.xcconfig')).write_text('OTHER_LDFLAGS = $(inherited) -lSystem\n')
            apps[1]['settings']['IPHONEOS_DEPLOYMENT_TARGET'] = '18.0'
            apps[1]['sources'] = [{'path': '/fixture/Widget.m'}]
            config = Config(job/'tools',job/'cache')
            with patch.object(expo,'run') as run:
                expo.compile_and_link(config,job,selected,apps)
                compile_calls = [call for call in run.call_args_list if str(call.args[0][1]).endswith('compile-pods.py')]
                self.assertEqual(compile_calls[0].args[0][-1], 'Widget')
            for app in apps:
                cmd = json.loads((job/'build/products'/app['name']/'link-command.json').read_text())
                self.assertEqual('-application_extension' in cmd, app['name']=='Widget')
                if app['name']=='Widget':
                    self.assertEqual(cmd[cmd.index('-platform_version')+2], '18.0')
                    self.assertIn('_NSExtensionMain',cmd)
                    self.assertIn('_main',cmd)
                    self.assertFalse(any('AppOnly' in arg for arg in cmd))

    def test_profiles_require_exact_coverage_and_app_group(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); app=root/'App.app'; app.mkdir()
            ext=app/'PlugIns/Widget.appex'; ext.mkdir(parents=True)
            for bundle, identity in ((app,'test.App'),(ext,'test.Widget')):
                (bundle/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':identity}))
            (root/'key').write_bytes(b'certificate')
            credentials=root/'credentials.json'
            credentials.write_text(json.dumps({'ios':{'main':{'distributionCertificate':{'path':'key','password':'p'},'provisioningProfilePath':'main'}}}))
            def decoded(identity):
                return type('Result',(),{'stdout':plistlib.dumps({'Entitlements':{'application-identifier':'TEAM.'+identity}})})()
            with patch.object(signing.subprocess,'run',return_value=decoded('test.App')):
                with self.assertRaisesRegex(ValueError,'Missing exact'): signing.check_bundle_profiles(app,credentials)
            entries=json.loads(credentials.read_text()); entries['ios']['widget']={**entries['ios']['main'],'provisioningProfilePath':'widget'}
            credentials.write_text(json.dumps(entries))
            requested=ext/'ios-anywhere-entitlements.plist'
            requested.write_bytes(plistlib.dumps({'com.apple.security.application-groups':['group.test']}))
            with patch.object(signing.subprocess,'run',side_effect=[decoded('test.App'),decoded('test.Widget')]):
                with self.assertRaisesRegex(ValueError,'does not authorize'): signing.check_bundle_profiles(app,credentials)
            requested.unlink()
            with patch.object(signing.subprocess,'run',side_effect=[decoded('test.App'),decoded('test.Widget')]):
                signing.check_bundle_profiles(app,credentials)
            (root/'other-key').write_bytes(b'other certificate')
            entries['ios']['widget']['distributionCertificate']={'path':'other-key','password':'p'}
            credentials.write_text(json.dumps(entries))
            with self.assertRaisesRegex(ValueError,'same distribution certificate'):
                signing.check_bundle_profiles(app,credentials)

    def test_widget_bundle_uses_widget_metro_and_bundle_container(self):
        with tempfile.TemporaryDirectory() as temp:
            job=Path(temp)
            (job/'build/app-resources').mkdir(parents=True)
            (job/'build/app-graph.json').write_text(json.dumps([target('App')]))
            (job/'build/pods-graph.json').write_text(json.dumps([target('ExpoWidgets')]))
            def emit(args, cwd, log, env):
                self.assertTrue(env['EXPO_OVERRIDE_METRO_CONFIG'].endswith('expo-widgets/metro.config.js'))
                output=Path(args[args.index('--bundle-output')+1])
                output.write_bytes(b'new widget javascript')
            with patch.object(expo,'run',side_effect=emit):
                expo.bundle_widgets(Config(job/'tools',job/'cache'),job)
            bundle=job/'build/app-resources/ExpoWidgets.bundle'
            self.assertEqual((bundle/'ExpoWidgets.bundle').read_bytes(),b'new widget javascript')
            self.assertEqual(plistlib.loads((bundle/'Info.plist').read_bytes())['CFBundlePackageType'],'BNDL')

    def test_clang_extension_safety_and_minimum_version(self):
        import os
        import runpy
        from ios_linux.config import SCRIPTS
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'headers/common').mkdir(parents=True)
            (root/'products').mkdir()
            extension=target('Widget','app-extension')
            extension['settings']['IPHONEOS_DEPLOYMENT_TARGET']='18.0'
            (root/'pods-graph.json').write_text('[]')
            (root/'app-graph.json').write_text(json.dumps([extension]))
            with patch.dict(os.environ,IOS_LINUX_TOOLCHAIN=str(root/'tools'),
                            IOS_LINUX_BUILD=str(root),IOS_LINUX_PROJECT=str(root/'project')):
                compiler=runpy.run_path(str(SCRIPTS/'compile-pods.py'))
                command,_=compiler['command'](extension,{'path':str(root/'Widget.mm')})
            self.assertIn('-fapplication-extension',command)
            self.assertEqual(command[command.index('-target')+1],'arm64-apple-ios18.0')
