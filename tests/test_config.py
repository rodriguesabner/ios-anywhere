import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ios_linux import cli
from ios_linux.config import Config, default_config


class ConfigDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / 'custom-config'
        self.env = patch.dict(os.environ, {'HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def write_config(self, name):
        path = self.root / name / 'config.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'toolchain': 'tools', 'cache': 'cache'}))
        return path

    def test_new_install_defaults_to_canonical_path(self):
        self.assertEqual(default_config(), self.root / 'ios-anywhere/config.json')
        self.assertFalse(self.root.exists())

    def test_home_used_when_xdg_unset_or_empty(self):
        with patch.dict(os.environ):
            os.environ.pop('XDG_CONFIG_HOME', None)
            self.assertEqual(default_config(), self.home / '.config/ios-anywhere/config.json')
            os.environ['XDG_CONFIG_HOME'] = ''
            self.assertEqual(default_config(), self.home / '.config/ios-anywhere/config.json')

    def test_canonical_config_under_xdg_is_loaded(self):
        path = self.write_config('ios-anywhere')
        self.assertEqual(default_config(), path)
        self.assertEqual(Config.load().toolchain, path.parent / 'tools')

    def test_legacy_fallback_keeps_paths_and_files(self):
        path = self.write_config('ios-linux')
        before = path.read_bytes()
        self.assertEqual(default_config(), path)
        self.assertEqual(Config.load().cache, path.parent / 'cache')
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.root / 'ios-anywhere').exists())

    def test_canonical_wins_when_both_exist(self):
        legacy = self.write_config('ios-linux')
        preferred = self.write_config('ios-anywhere')
        before = legacy.read_bytes()
        self.assertEqual(default_config(), preferred)
        self.assertEqual(Config.load().toolchain, preferred.parent / 'tools')
        self.assertEqual(legacy.read_bytes(), before)

    def test_invalid_canonical_does_not_silently_fall_back(self):
        self.write_config('ios-linux')
        preferred = self.write_config('ios-anywhere')
        preferred.write_text('invalid json')
        with self.assertRaises(json.JSONDecodeError):
            Config.load()

    def test_dangling_canonical_symlink_does_not_silently_fall_back(self):
        legacy = self.write_config('ios-linux')
        before = legacy.read_bytes()
        preferred = self.root / 'ios-anywhere/config.json'
        preferred.parent.mkdir(parents=True)
        missing = preferred.parent / 'missing.json'
        preferred.symlink_to(missing)

        self.assertFalse(preferred.exists())
        self.assertEqual(default_config(), preferred)
        with self.assertRaisesRegex(ValueError, 'Configuration not found') as error:
            Config.load()
        self.assertIn(str(missing), str(error.exception))
        self.assertTrue(preferred.is_symlink())
        self.assertFalse(missing.exists())
        self.assertEqual(legacy.read_bytes(), before)

    def test_valid_canonical_symlink_loads_target_over_legacy(self):
        self.write_config('ios-linux')
        target = self.write_config('linked')
        preferred = self.root / 'ios-anywhere/config.json'
        preferred.parent.mkdir(parents=True)
        preferred.symlink_to(target)

        self.assertEqual(default_config(), preferred)
        self.assertEqual(Config.load().toolchain, target.parent / 'tools')

    def test_explicit_cli_config_wins_over_both_defaults(self):
        self.write_config('ios-linux')
        self.write_config('ios-anywhere')
        explicit = self.write_config('explicit')
        with patch.object(Config, 'doctor', autospec=True) as doctor:
            cli.execute(['--config', str(explicit), 'doctor'])
        config, engine = doctor.call_args.args
        self.assertEqual(config.toolchain, explicit.parent / 'tools')
        self.assertEqual(engine, 'expo')

    def test_missing_explicit_config_does_not_fall_back(self):
        self.write_config('ios-linux')
        self.write_config('ios-anywhere')
        with self.assertRaisesRegex(ValueError, 'Configuration not found'):
            Config.load(self.root / 'missing.json')
