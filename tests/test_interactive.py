import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from ios_linux import cli, interactive


class InteractiveTests(unittest.TestCase):
    def test_godot_build_uses_existing_argument_contract(self):
        with patch.object(interactive, 'choose', side_effect=['build', 'godot']), \
             patch.object(interactive, 'select_config', return_value='/config.json'), \
             patch.object(interactive, 'path_prompt', side_effect=['/my game', '/private/creds.json', '/new.ipa']), \
             patch.object(interactive, 'ask', return_value='com.example.game'):
            args = cli.parser().parse_args(interactive.arguments())
        self.assertEqual(args.engine, 'godot')
        self.assertEqual(args.project, Path('/my game'))
        self.assertEqual(args.bundle_id, 'com.example.game')
        self.assertEqual(args.credentials, Path('/private/creds.json'))
        self.assertEqual(args.output, Path('/new.ipa'))

    def test_expo_setup_keeps_confirmations_and_explicit_paths(self):
        for source in ('mirror', 'local'):
            with self.subTest(source=source), patch.object(interactive, 'choose', side_effect=['setup', 'expo', source]), \
                 patch.object(interactive, 'path_prompt', side_effect=['/new.json', '/new-tools', '/sdks']):
                args = cli.parser().parse_args(interactive.arguments())
            self.assertEqual(args.command, 'setup')
            self.assertEqual(args.setup_engine, 'expo')
            self.assertFalse(args.yes)
            self.assertEqual(args.sdk_source, source)
            self.assertEqual(args.sdk, Path('/sdks') if source == 'local' else None)

    def test_doctor_and_bundle_routes(self):
        for action in ('doctor', 'bundle'):
            with patch.object(interactive, 'choose', side_effect=[action, 'expo']), \
                 patch.object(interactive, 'select_config', return_value='/expo.json'), \
                 patch.object(interactive, 'path_prompt', return_value='/project'):
                args = cli.parser().parse_args(interactive.arguments())
            self.assertEqual(args.command, action)
            self.assertEqual(args.engine, 'expo')
            self.assertIsNone(args.credentials)

    def test_install_and_verify_do_not_ask_for_engine(self):
        for action in ('install', 'verify'):
            with patch.object(interactive, 'choose', return_value=action) as choose, \
                 patch.object(interactive, 'select_config', return_value='/config.json'), \
                 patch.object(interactive, 'path_prompt', return_value='/app.ipa'), \
                 patch.object(interactive, 'ask', return_value='device-id'):
                args = cli.parser().parse_args(interactive.arguments())
            choose.assert_called_once()
            self.assertEqual(args.command, action)
            self.assertEqual(args.ipa, Path('/app.ipa'))

    def test_config_discovery_preserves_files_and_expands_home(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'HOME': temp, 'XDG_CONFIG_HOME': temp + '/configs'}):
            root = Path(temp) / 'configs'
            for folder in ('ios-linux', 'ios-anywhere'):
                (root / folder).mkdir(parents=True)
                (root / folder / 'config.json').write_text('{}')
            (root / 'ios-anywhere/expo.json').write_text('{}')
            found = interactive.configurations()
            self.assertEqual(len(found), 3)
            self.assertEqual(found[0], root / 'ios-anywhere/config.json')
            self.assertEqual(interactive.validate_path('~/configs', 'directory'), True)
            self.assertNotEqual(interactive.validate_path('~/configs', 'new'), True)
            self.assertNotEqual(interactive.validate_path('', 'file'), True)
            with patch.object(interactive, 'ask', return_value='~/configs'):
                self.assertEqual(interactive.path_prompt('Path', 'directory'), str(root))

    def test_cancellation_never_executes_a_command(self):
        with patch.object(cli.sys.stdin, 'isatty', return_value=True), \
             patch.object(cli.sys.stdout, 'isatty', return_value=True), \
             patch.object(interactive, 'arguments', side_effect=KeyboardInterrupt), \
             patch.object(cli.Config, 'load') as load:
            self.assertEqual(cli.main([]), 130)
            load.assert_not_called()
        questionary = Mock()
        questionary.select.return_value.ask.return_value = None
        with patch.dict('sys.modules', {'questionary': questionary}):
            with self.assertRaises(KeyboardInterrupt):
                interactive.ask('select', 'Cancel')

    def test_no_arguments_only_prompts_in_a_terminal(self):
        with patch.object(cli.sys.stdin, 'isatty', return_value=False), \
             patch.object(interactive, 'arguments') as prompt:
            with self.assertRaises(SystemExit):
                cli.execute([])
            prompt.assert_not_called()
        with patch.object(cli.sys.stdin, 'isatty', return_value=True), \
             patch.object(cli.sys.stdout, 'isatty', return_value=True), \
             patch.object(interactive, 'arguments', return_value=None), \
             patch.object(cli.Config, 'load') as load:
            cli.execute([])
            load.assert_not_called()

    def test_explicit_commands_bypass_menu(self):
        with patch.object(interactive, 'arguments') as prompt:
            with self.assertRaises(SystemExit) as result:
                cli.execute(['--help'])
            self.assertEqual(result.exception.code, 0)
            prompt.assert_not_called()
