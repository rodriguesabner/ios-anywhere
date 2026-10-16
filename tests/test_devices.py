import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock
import zipfile

from ios_linux import cli, devices, provisioning, interactive
from ios_linux.config import Config

UDID = '00008000-0000000000000001'


class DeviceTests(unittest.TestCase):
    def test_save_replace_and_discovery(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'XDG_CONFIG_HOME': temp}):
            devices.save('Phone', UDID.lower())
            devices.save('Renamed phone', UDID)
            self.assertEqual(devices.load(), [{'name': 'Renamed phone', 'udid': UDID}])
            self.assertEqual(devices.store_path().stat().st_mode & 0o777, 0o600)
            self.assertEqual(interactive.configurations(), [])
            with patch.object(interactive, 'choose', return_value=UDID):
                self.assertEqual(devices.select(), UDID)
            devices.store_path().write_text('{}')
            with self.assertRaises(ValueError):
                devices.save('Another', UDID)
            self.assertEqual(devices.store_path().read_text(), '{}')

    def test_udid_validation(self):
        for invalid in ('', 'serial-number', '../x', None):
            with self.assertRaises(ValueError):
                devices.validate_udid(invalid)
        self.assertEqual(devices.validate_udid('a' * 40), 'A' * 40)

    def test_all_extension_profiles_must_include_device(self):
        with tempfile.TemporaryDirectory() as temp:
            ipa = Path(temp) / 'app.ipa'
            with zipfile.ZipFile(ipa, 'w') as z:
                for root in ('Payload/Game.app/', 'Payload/Game.app/PlugIns/Widget.appex/'):
                    z.writestr(root + 'Info.plist', b'')
                    z.writestr(root + 'embedded.mobileprovision', b'profile')
            included = Mock(stdout=plistlib.dumps({'ProvisionedDevices': [UDID.lower()]}))
            excluded = Mock(stdout=plistlib.dumps({'ProvisionedDevices': []}))
            with patch.object(devices.subprocess, 'run', return_value=included):
                devices.check_ipa(ipa, UDID)
            with patch.object(devices.subprocess, 'run', side_effect=[included, excluded]):
                with self.assertRaisesRegex(ValueError, 'Widget.appex'):
                    devices.check_ipa(ipa, UDID)

    def test_install_never_runs_after_failed_profile_check(self):
        with tempfile.TemporaryDirectory() as temp:
            ipa = Path(temp) / 'app.ipa'
            ipa.touch()
            with patch.object(Config, 'load', return_value=Config(Path('/tools'), Path('/cache'))), \
                 patch.object(cli.shutil, 'which', return_value='/installer'), \
                 patch.object(devices, 'check_ipa', side_effect=ValueError('not included')), \
                 patch.object(cli.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'not included'):
                    cli.execute(['install', str(ipa), '--udid', UDID])
                run.assert_not_called()

    def test_signing_setup_menu(self):
        with patch.object(interactive, 'choose', return_value='signing-setup'), \
             patch.object(interactive, 'select_config', return_value='/config.json'), \
             patch.object(interactive, 'path_prompt', return_value='/private/new'):
            args = cli.parser().parse_args(interactive.arguments())
            self.assertEqual(args.command, 'signing-setup')
            self.assertEqual(args.output, Path('/private/new'))

    def test_provisioning_preserves_existing_folder_and_cancelled_download(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'XDG_DATA_HOME': temp}):
            config = Config(Path('/tools'), Path('/cache'))
            with self.assertRaises(ValueError):
                provisioning.setup(config, Path(temp))
            with patch.object(provisioning.shutil, 'which', return_value='/tool'), \
                 patch.object(interactive, 'ask', return_value=False), \
                 patch.object(provisioning.subprocess, 'run') as run:
                provisioning.setup(config, Path(temp) / 'new')
                run.assert_not_called()
