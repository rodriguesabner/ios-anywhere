from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ios_linux import interactive as ui, wizard


class WizardTests(unittest.TestCase):
    def setUp(self):
        for target, value in [('ios_linux.config.Config.load', None),
                              ('ios_linux.expo.bundle_identifier', 'com.example.app'),
                              ('ios_linux.signing.check_identity', None)]:
            mock = patch(target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_reuse_and_install_retry_never_rebuilds(self):
        calls = []
        def command(argv):
            calls.append(argv)
            if 'install' in argv and sum('install' in c for c in calls) == 1:
                raise ValueError('phone disconnected')
        with patch.object(ui, 'choose', side_effect=['expo', 'existing', 'existing', 'build']), \
             patch.object(ui, 'select_config', return_value='/expo.json'), \
             patch.object(ui, 'path_prompt', side_effect=['/project', '/credentials.json', '/app.ipa']), \
             patch.object(ui, 'ask', side_effect=[True, True]), \
             patch('ios_linux.devices.select', return_value='test-device'), \
             patch('ios_linux.cli.execute', side_effect=command):
            wizard.run()
        self.assertEqual(sum('build' in c for c in calls), 1)
        self.assertEqual(sum('install' in c for c in calls), 2)
        self.assertFalse(any('setup' in c or 'signing-setup' in c for c in calls))

    def test_cancel_review_does_not_build(self):
        with patch.object(ui, 'choose', side_effect=['expo', 'existing', 'existing', 'cancel']), \
             patch.object(ui, 'select_config', return_value='/expo.json'), \
             patch.object(ui, 'path_prompt', side_effect=['/project', '/credentials.json', '/app.ipa']), \
             patch('ios_linux.cli.execute') as command:
            wizard.run()
        self.assertEqual(command.call_count, 1)
        self.assertEqual(command.call_args.args[0][-1], 'doctor')

    def test_cancelled_setup_never_advances_to_doctor(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(ui, 'choose', side_effect=['expo', 'new', 'back']), \
             patch.object(ui, 'arguments', return_value=['--config', str(Path(temp) / 'missing.json'), 'setup']), \
             patch('ios_linux.cli.execute') as command:
            wizard.run()
        self.assertEqual(command.call_count, 1)

    def test_failed_check_returns_to_tool_selection(self):
        with patch.object(ui, 'choose', side_effect=['expo', 'existing', 'back']), \
             patch.object(ui, 'select_config', return_value='/wrong.json'), \
             patch.object(ui, 'ask', return_value=False), \
             patch('ios_linux.cli.execute', side_effect=ValueError('wrong tools')) as command:
            wizard.run()
        self.assertEqual(command.call_count, 1)

    def test_signing_cancel_can_reuse_credentials(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(ui, 'choose', side_effect=['expo', 'existing', 'new', 'existing', 'build']), \
             patch.object(ui, 'select_config', return_value='/expo.json'), \
             patch.object(ui, 'signing_folder', return_value=temp), \
             patch.object(ui, 'path_prompt', side_effect=['/project', '/credentials.json', '/app.ipa']), \
             patch.object(ui, 'ask', return_value=False), \
             patch('ios_linux.cli.execute') as command:
            wizard.run()
        self.assertEqual(sum('signing-setup' in c.args[0] for c in command.call_args_list), 1)
        self.assertIn('/credentials.json', command.call_args.args[0])

    def test_back_from_submenu(self):
        with patch.object(ui, 'choose', side_effect=['advanced', 'back', 'manage', 'device']):
            self.assertEqual(ui.menu(), 'device')

    def test_config_labels_do_not_read_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'expo.json'
            path.write_text('{"toolchain": "/tools", "password": "private"}')
            label = ui.config_label(path)
            self.assertIn('Expo / React Native', label)
            self.assertIn('/tools', label)
            self.assertNotIn('private', label)
