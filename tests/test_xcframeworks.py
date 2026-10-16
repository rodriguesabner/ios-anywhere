from pathlib import Path
import plistlib
import tempfile
import unittest
from ios_linux.expo import static_xcframework_paths


def bundle(root, name='skia', platform='ios', variant=None, identifier='ios-arm64_arm64e'):
    folder = root / f'lib{name}.xcframework'
    archive = folder / identifier / f'lib{name}.a'
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b'fixture')
    entry = {'LibraryPath': archive.name, 'LibraryIdentifier': identifier,
             'SupportedPlatform': platform, 'SupportedArchitectures': ['arm64', 'arm64e']}
    if variant:
        entry['SupportedPlatformVariant'] = variant
    (folder / 'Info.plist').write_bytes(plistlib.dumps({'AvailableLibraries': [entry]}))
    return folder, archive


class XCFrameworkTests(unittest.TestCase):
    def test_local_pod_static_slice_is_added_without_simulator_or_unused_libraries(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / 'node_modules/@shopify/react-native-skia'
            _, archive = bundle(source / 'libs/apple')
            bundle(source / 'unused', name='skottie')
            bundle(project / 'ios/Pods/simulator', variant='simulator')
            bundle(project / 'ios/Pods/tvos', platform='tvos')
            targets = [{'settings': {'PODS_TARGET_SRCROOT': str(source)}}]
            self.assertEqual(static_xcframework_paths(project, targets, ['-lskia']), ['-L' + str(archive.parent)])

    def test_relative_local_pod_root_and_duplicate_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            _, archive = bundle(project / 'ios/Pods/local')
            targets = [{'settings': {'PODS_TARGET_SRCROOT': 'local'}}]
            self.assertEqual(static_xcframework_paths(project, targets, ['-lskia']), ['-L' + str(archive.parent)])

    def test_missing_or_escaping_archive_fails(self):
        for escaping in (False, True):
            with self.subTest(escaping=escaping), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp)
                folder, archive = bundle(project / 'ios/Pods')
                archive.unlink()
                if escaping:
                    outside = project / 'outside.a'
                    outside.touch()
                    archive.symlink_to(outside)
                with self.assertRaisesRegex(ValueError, 'Invalid or missing'):
                    static_xcframework_paths(project, [], ['-lskia'])

    def test_conflicting_libraries_are_not_selected_arbitrarily(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            bundle(project / 'ios/Pods/one')
            bundle(project / 'ios/Pods/two')
            with self.assertRaisesRegex(ValueError, 'Ambiguous'):
                static_xcframework_paths(project, [], ['-lskia'])
