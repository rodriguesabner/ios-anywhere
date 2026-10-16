import fcntl
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ios_linux.config import Config
from ios_linux import cleanup, interactive, cli


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = Config(self.root / 'tools', self.root / 'cache')
        self.job = self.config.cache / 'expo/test'
        (self.job / 'project').mkdir(parents=True)
        (self.job / 'project/package.json').write_text('{}')
        (self.job / 'build').mkdir()
        (self.job / 'build/object.o').write_text('generated')
        (self.job / 'build.log').write_text('evidence')
        (self.job / 'project/credentials.json').write_text('private')
        (self.job / 'output.ipa').write_text('keep')

    def test_confirm_removes_only_generated_files(self):
        with patch.object(interactive, 'ask', return_value=True):
            cleanup.clean(self.config)
        self.assertFalse((self.job / 'build').exists())
        for name in ('build.log', 'output.ipa', 'project/package.json', 'project/credentials.json'):
            self.assertTrue((self.job / name).is_file())
        self.assertTrue((self.config.cache / 'build.lock').exists())

    def test_cancel_preserves_files(self):
        with patch.object(interactive, 'ask', return_value=False):
            cleanup.clean(self.config)
        self.assertTrue((self.job / 'build/object.o').is_file())

    def test_active_build_blocks_cleanup(self):
        with (self.config.cache / 'build.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'build is running'):
                cleanup.clean(self.config)
        self.assertTrue((self.job / 'build/object.o').exists())

    def test_links_and_unknown_folders_are_preserved(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'keep').write_text('keep')
        (self.job / 'project/node_modules').symlink_to(outside, target_is_directory=True)
        (self.job / 'build/external').symlink_to(outside, target_is_directory=True)
        unknown = self.config.cache / 'expo/unknown/build'
        unknown.mkdir(parents=True)
        with patch.object(interactive, 'ask', return_value=True):
            cleanup.clean(self.config)
        self.assertTrue((outside / 'keep').exists())
        self.assertTrue((self.job / 'project/node_modules').is_symlink())
        self.assertTrue(unknown.exists())

    def test_unsafe_root_is_rejected(self):
        with self.assertRaises(ValueError):
            cleanup.candidates(Config(self.root / 'cache/tools', self.root / 'cache'))

    def test_menu_does_not_require_engine(self):
        with patch.object(interactive, 'choose', return_value='clean'), patch.object(interactive, 'select_config', return_value='/config.json'):
            args = cli.parser().parse_args(interactive.arguments())
        self.assertEqual(args.command, 'clean')
        self.assertIsNone(args.engine)
