import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from ios_linux import cli, setup, setup_expo, expo
from ios_linux.config import Config


class ExpoSetupTests(unittest.TestCase):
    def test_unsupported_host_fails_before_changes(self):
        with patch.object(setup_expo.platform, 'freedesktop_os_release', return_value={'ID': 'debian', 'VERSION_ID': '13'}):
            with self.assertRaisesRegex(ValueError, 'Ubuntu 24.04'):
                setup_expo.check_host()

    def test_expo_low_space_stops_before_downloads_or_apt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = cli.parser().parse_args(['--config', str(root / 'config.json'), 'setup', '--engine', 'expo', '--toolchain', str(root / 'tools'), '--sdk-source', 'mirror', '--yes'])
            with patch.object(setup_expo, 'check_host'), patch.object(setup.shutil, 'disk_usage') as usage, patch.object(setup, 'run') as run:
                usage.return_value.free = 10 * 1024**3
                with self.assertRaisesRegex(ValueError, '20 GiB'):
                    setup.setup(args)
                run.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])

    def test_local_node_precedes_system_node_in_build_env(self):
        config = Config(Path('/tools'), Path('/cache'))
        self.assertEqual(config.env()['PATH'].split(os.pathsep)[0], '/tools/node/bin')
        env = expo.tool_env(config, Path('/project'), Path('/build'))
        self.assertIn('/tools/node/bin', env['PATH'].split(os.pathsep))

    def test_archive_root_and_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, safe in [('swift/usr/bin/swiftc', True), ('../escape', False)]:
                archive = root / 'tools.tar'
                with tarfile.open(archive, 'w') as tar:
                    entry = tarfile.TarInfo(name)
                    entry.size = 4
                    tar.addfile(entry, io.BytesIO(b'tool'))
                if safe:
                    setup_expo.extract_root(archive, root / 'swift', 'usr/bin/swiftc')
                    self.assertEqual((root / 'swift/usr/bin/swiftc').read_bytes(), b'tool')
                else:
                    with self.assertRaises(tarfile.FilterError):
                        setup_expo.extract_root(archive, root / 'bad', 'usr/bin/swiftc')
                    self.assertFalse((root / 'escape').exists())

    def test_mirror_patch_rejects_unknown_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            tools = Path(temp)
            stub = tools / 'sdks/iPhoneOS26.5.sdk/System/Library/PrivateFrameworks/UIKitCore.framework/UIKitCore.tbd'
            stub.parent.mkdir(parents=True)
            stub.write_text('different SDK')
            with self.assertRaisesRegex(ValueError, 'refusing to patch'):
                setup_expo.patch_mirror_sdk(tools)
            self.assertEqual(stub.read_text(), 'different SDK')
            with patch.object(setup, 'sha256', return_value=setup_expo.UIKIT_STUB_HASH):
                setup_expo.patch_mirror_sdk(tools)
            self.assertFalse(stub.exists())
            self.assertEqual(stub.with_suffix('.tbd.mirror-backup').read_text(), 'different SDK')

    def test_swift_overlays_are_local_and_do_not_modify_compiler(self):
        with tempfile.TemporaryDirectory() as temp:
            tools = Path(temp)
            linux = tools / 'swift/usr/lib/swift/linux'
            original = '// swift-module-flags: -target x86_64-unknown-linux-gnu -disable-objc-interop\n'
            for module in ['Cxx', 'CxxStdlib']:
                source = linux / f'{module}.swiftmodule/x86_64-unknown-linux-gnu.swiftinterface'
                source.parent.mkdir(parents=True)
                source.write_text(original)
            for name in ['libcxxshim.h', 'libcxxshim.modulemap', 'libcxxstdlibshim.h']:
                (linux / name).write_text(name)
            setup_expo.prepare_overlays(tools)
            target = tools / 'darwin-resource/iphoneos/Cxx.swiftmodule/arm64-apple-ios.swiftinterface'
            self.assertIn('arm64-apple-ios16.4 -enable-objc-interop', target.read_text())
            self.assertEqual(source.read_text(), original)
            self.assertFalse(os.path.isabs(os.readlink(tools / 'darwin-resource/shims')))

    def test_expo_publish_requires_successful_native_check(self):
        for fail in (True, False):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                config, tools = root / 'config.json', root / 'tools'
                args = cli.parser().parse_args(['--config', str(config), 'setup', '--engine', 'expo', '--toolchain', str(tools), '--sdk-source', 'mirror', '--yes'])
                with patch.object(setup_expo, 'check_host'), patch.object(setup, 'check_space') as space, \
                     patch.object(setup.shutil, 'which', return_value='/usr/bin/tool'), \
                     patch.object(setup, 'run'), patch.object(setup, 'install_tools') as godot, \
                     patch.object(setup_expo, 'install_tools'), patch.object(setup, 'install_sdk') as sdk, \
                     patch.object(setup_expo, 'patch_mirror_sdk'), patch.object(setup_expo, 'prepare_runtime'), \
                     patch.object(setup_expo, 'smoke_test', side_effect=ValueError('Swift failed') if fail else None):
                    if fail:
                        with self.assertRaisesRegex(ValueError, 'Swift failed'):
                            setup.setup(args)
                        self.assertFalse(tools.exists())
                        self.assertFalse(config.exists())
                    else:
                        setup.setup(args)
                        self.assertEqual(json.loads(config.read_text())['llvm_ar'], 'llvm-ar-18')
                        self.assertEqual(json.loads((tools / 'setup-manifest.json').read_text())['engine'], 'expo')
                    space.assert_called_once_with(root, 20 * 1024**3)
                    godot.assert_not_called()
                    self.assertEqual([call.args[3] for call in sdk.call_args_list], ['26.4', '26.5'])
