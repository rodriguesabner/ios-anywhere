import json
import plistlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from ios_linux import expo, signing


class IdentityTests(unittest.TestCase):
    def test_static_missing_and_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'app.json').write_text('{"expo": {}}')
            with self.assertRaisesRegex(ValueError, 'ios.bundleIdentifier'):
                expo.bundle_identifier(None, root)
            (root / 'app.json').write_text('{"expo":{"ios":{"bundleIdentifier":"com.example.app"}}}')
            self.assertEqual(expo.bundle_identifier(None, root), 'com.example.app')

    def test_dynamic_overrides_static(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'app.config.ts').touch()
            (root / 'app.json').write_text('{}')
            cli = root / 'node_modules/expo/bin/cli'
            cli.parent.mkdir(parents=True)
            cli.touch()
            config = Mock()
            config.env.return_value = {}
            with patch.object(expo.subprocess, 'run', return_value=Mock(returncode=0, stdout='{"ios":{"bundleIdentifier":"com.dynamic.app"}}')):
                self.assertEqual(expo.bundle_identifier(config, root), 'com.dynamic.app')

    def test_profile_exact_match_and_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'cert.p12').touch()
            (root / 'app.mobileprovision').touch()
            creds = root / 'credentials.json'
            creds.write_text(json.dumps({'ios': {'distributionCertificate': {'path': 'cert.p12', 'password': ''},
                                                 'provisioningProfilePath': 'app.mobileprovision'}}))
            for identity, valid in [('TEAM.com.example.app', True), ('TEAM.com.other.app', False), ('TEAM.com.example.*', False)]:
                result = Mock(returncode=0, stdout=plistlib.dumps({'Entitlements': {'application-identifier': identity}}))
                with patch.object(signing.subprocess, 'run', return_value=result):
                    if valid:
                        signing.check_identity(creds, 'com.example.app')
                    else:
                        with self.assertRaisesRegex(ValueError, 'does not match'):
                            signing.check_identity(creds, 'com.example.app')

    def test_mismatch_stops_before_prepare(self):
        with patch.object(signing, 'check_output'), patch.object(signing, 'check_credentials'), \
             patch.object(Path, 'is_file', return_value=True), \
             patch.object(Path, 'read_text', return_value='{"ios":true}'), \
             patch.object(expo, 'bundle_identifier', return_value='com.example.app'), \
             patch.object(signing, 'check_identity', side_effect=ValueError('mismatch')), \
             patch.object(expo, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                expo.build(None, Path('/project'), Path('/app.ipa'), Path('/credentials.json'))
            prepare.assert_not_called()
