import json
from pathlib import Path
import tempfile
import unittest
from ios_linux import expo as expo_backend


class ExpoTests(unittest.TestCase):
    def test_constants_resolution_supports_nested_and_hoisted_packages(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            expo = project / "node_modules/expo"
            expo.mkdir(parents=True)
            (expo / "package.json").write_text('{"name":"expo"}')
            nested = expo / "node_modules/expo-constants/scripts/getAppConfig.js"
            nested.parent.mkdir(parents=True)
            nested.touch()
            (nested.parent.parent / "package.json").write_text(
                '{"exports":{"./package.json":"./package.json"}}'
            )
            self.assertEqual(expo_backend.constants_script(project), nested)
            hoisted = project / "node_modules/expo-constants/scripts/getAppConfig.js"
            hoisted.parent.mkdir(parents=True)
            hoisted.touch()
            (hoisted.parent.parent / "package.json").write_text(
                '{"exports":{"./package.json":"./package.json"}}'
            )
            self.assertEqual(expo_backend.constants_script(project), hoisted)

    def test_splash_patch_is_idempotent_and_keeps_existing_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            source = (
                project
                / "node_modules/expo-splash-screen/ios/SplashScreenManager.swift"
            )
            source.parent.mkdir(parents=True)
            original = "    if let vc = UIStoryboard(name: splashScreenFilename, bundle: nil).instantiateInitialViewController() {\n      loadingView = vc.view\n    }"
            source.write_text(original)
            expo_backend.patch_splash(project)
            first = source.read_text()
            self.assertIn(original, first)
            self.assertIn('ofType: "storyboardc"', first)
            expo_backend.patch_splash(project)
            self.assertEqual(source.read_text(), first)

    def test_scene_patch_is_idempotent_and_preserves_app_setup(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            path = project / "ios/App/AppDelegate.swift"
            path.parent.mkdir(parents=True)
            path.write_text(
                'setupBefore()\n    window = UIWindow(frame: UIScreen.main.bounds)\n    factory.startReactNative(\n      withModuleName: "main",\n      in: window,\n      launchOptions: launchOptions)\nsetupAfter()\n'
            )
            apps = [{"name": "App"}]
            expo_backend.patch_scene(project, apps)
            first = path.read_text()
            self.assertIn("setupBefore()", first)
            self.assertIn("setupAfter()", first)
            self.assertNotIn("UIScreen.main.bounds", first)
            self.assertIn("UIWindow(windowScene: scene)", first)
            expo_backend.patch_scene(project, apps)
            self.assertEqual(path.read_text(), first)

    def test_native_patch_preserves_boxed_values_and_other_constants(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            source = (
                project
                / "node_modules/react-native-screens/ios/RNSScreenStackHeaderConfig.mm"
            )
            source.parent.mkdir(parents=True)
            source.write_text(
                "static constexpr auto DEFAULT_TITLE_FONT_SIZE = @17;\nstatic constexpr int other = 99;"
            )
            expo_backend.patch_native_sources(project)
            self.assertEqual(
                source.read_text(),
                "static const auto DEFAULT_TITLE_FONT_SIZE = @17;\nstatic constexpr int other = 99;",
            )

    def test_external_stage_uses_project_identity_and_version(self):
        import plistlib

        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            (job / "project/ios/Other").mkdir(parents=True)
            (job / "build/products/Other").mkdir(parents=True)
            (job / "build/products/Other/Other").write_bytes(b"linked")
            (job / "build/app-resources").mkdir()
            (job / "build/app-resources/main.jsbundle").write_bytes(b"javascript")
            (job / "project/ios/Other/Info.plist").write_bytes(
                plistlib.dumps(
                    {
                        "CFBundleIdentifier": "$(PRODUCT_BUNDLE_IDENTIFIER)",
                        "CFBundleVersion": "$(CURRENT_PROJECT_VERSION)",
                    }
                )
            )
            (job / "build/pods-graph.json").write_text("[]")
            (job / "build/app-graph.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "Other",
                            "settings": {
                                "INFOPLIST_FILE": "Other/Info.plist",
                                "PRODUCT_BUNDLE_IDENTIFIER": "com.test.other",
                                "CURRENT_PROJECT_VERSION": "42",
                            },
                        }
                    ]
                )
            )
            app = expo_backend.stage(job)
            self.assertEqual(app.name, "Other.app")
            info = plistlib.loads((app / "Info.plist").read_bytes())
            self.assertEqual(info["CFBundleIdentifier"], "com.test.other")
            self.assertEqual(info["CFBundleVersion"], "42")
            self.assertFalse((app / "PlugIns").exists())
            self.assertEqual(info["MinimumOSVersion"], "16.4")
            scene = info["UIApplicationSceneManifest"]["UISceneConfigurations"][
                "UIWindowSceneSessionRoleApplication"
            ][0]
            self.assertEqual(scene["UISceneDelegateClassName"], "Other.SceneDelegate")
            (job / "build/pods-graph.json").write_text(
                json.dumps(
                    [
                        {
                            "settings": {"SWIFT_OBJC_INTEROP_MODE": "objcxx"},
                            "resources": [],
                        }
                    ]
                )
            )
            app = expo_backend.stage(job)
            self.assertEqual(
                plistlib.loads((app / "Info.plist").read_bytes())["MinimumOSVersion"],
                "27.0",
            )
