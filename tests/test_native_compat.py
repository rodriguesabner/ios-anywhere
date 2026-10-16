import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
from ios_linux import expo
from ios_linux.config import Config, SCRIPTS


class NativeCompatTests(unittest.TestCase):
    def test_recursive_header_paths_expand_without_losing_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            headers = root / 'my headers'
            (headers / 'api/third_party').mkdir(parents=True)
            (headers / 'api/third_party/base64.h').touch()
            (root / 'pods-graph.json').write_text('[]')
            env = {'IOS_LINUX_TOOLCHAIN': str(root), 'IOS_LINUX_BUILD': str(root), 'IOS_LINUX_PROJECT': str(root)}
            with patch.dict(os.environ, env):
                compiler = runpy.run_path(str(SCRIPTS / 'compile-pods.py'))
            target = {'name': 'Skia', 'settings': {'HEADER_SEARCH_PATHS': f'"{headers}/"/**'}}
            cmd, _ = compiler['command'](target, {'path': str(root / 'base64.cpp')})
            self.assertIn(str(headers / 'api'), cmd)
            self.assertIn(str(headers / 'api/third_party'), cmd)
            self.assertFalse(any('**' in arg for arg in cmd))
            self.assertFalse(any(arg.endswith('base64.h') for arg in cmd))
            self.assertIn('-DFMT_USE_CONSTEVAL=0', cmd)
            ccmd, _ = compiler['command'](target, {'path': str(root / 'source.c')})
            self.assertNotIn('-DFMT_USE_CONSTEVAL=0', ccmd)

    def test_glog_repairs_cached_probes_preserving_apple_tail_and_textual_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            header = root / 'ios/Pods/glog/src/config.h'
            header.parent.mkdir(parents=True)
            suffix = '/* Add in so we have Apple Target Conditionals */\n#include <TargetConditionals.h>\n'
            header.write_text('/* #undef HAVE_PTHREAD */\n/* #undef HAVE_PREAD */\n' + suffix)
            header.chmod(0o444)
            modulemap = root / 'ios/Pods/Target Support Files/glog/glog.modulemap'
            modulemap.parent.mkdir(parents=True)
            modulemap.write_text('module glog {\n umbrella header "glog-umbrella.h"\n export *\n module * { export * }\n}\n')
            def configure(*args):
                self.assertEqual(Path(args[0][0]).name, 'clang')
                self.assertFalse((header.parent.parent / 'configure').exists())
                self.assertIn('pthread_create', (root / 'glog-ios-probe.c').read_text())
            with patch.object(expo, 'run', side_effect=configure) as run:
                config = Config(root / 'tools', root / 'cache')
                expo.prepare_glog(config, root, root, root)
                expo.prepare_glog(config, root, root, root)
                run.assert_called_once()
            self.assertTrue(header.read_text().endswith(suffix))
            self.assertIn('#define HAVE_PTHREAD 1', header.read_text())
            self.assertIn('#define HAVE_PREAD 1', header.read_text())
            self.assertIn('textual header', modulemap.read_text())
            self.assertNotIn('umbrella header', modulemap.read_text())
            self.assertNotIn('module *', modulemap.read_text())

    def test_glog_failed_probes_stop_instead_of_disabling_threads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            header = root / 'ios/Pods/glog/src/config.h'
            header.parent.mkdir(parents=True)
            original = '/* #undef HAVE_PTHREAD */\n/* #undef HAVE_PREAD */\n'
            header.write_text(original)
            with patch.object(expo, 'run', side_effect=ValueError('Step glog-probe failed')), self.assertRaisesRegex(ValueError, 'glog-probe'):
                expo.prepare_glog(Config(root, root), root, root, root)
            self.assertEqual(header.read_text(), original)

    def test_fmt_override_guard_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            header = project / 'ios/Pods/fmt/include/fmt/base.h'
            header.parent.mkdir(parents=True)
            header.write_text('#if !defined(__cpp_lib_is_constant_evaluated)\n#define FMT_USE_CONSTEVAL 0\n#else\n#define FMT_USE_CONSTEVAL 1\n#endif\n')
            expo.patch_native_sources(project)
            patched = header.read_text()
            self.assertIn('#if defined(FMT_USE_CONSTEVAL)', patched)
            expo.patch_native_sources(project)
            self.assertEqual(patched, header.read_text())

    def test_read_only_fmt_is_patchable_without_changing_other_pods(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            header = project / 'ios/Pods/fmt/include/fmt/base.h'
            header.parent.mkdir(parents=True)
            header.write_text('#if !defined(__cpp_lib_is_constant_evaluated)\n#endif\n')
            header.chmod(0o444)
            unrelated = project / 'ios/Pods/other.h'
            unrelated.write_text('unchanged')
            unrelated.chmod(0o444)
            external = project / 'external.h'
            external.write_text('outside pod')
            external.chmod(0o444)
            (header.parent / 'external.h').symlink_to(external)
            expo.patch_native_sources(project)
            self.assertIn('#if defined(FMT_USE_CONSTEVAL)', header.read_text())
            self.assertEqual(header.stat().st_mode & 0o777, 0o644)
            self.assertEqual(unrelated.stat().st_mode & 0o777, 0o444)
            self.assertEqual(external.stat().st_mode & 0o777, 0o444)

    def test_symlinked_pod_is_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / 'ios/Pods').mkdir(parents=True)
            (project / 'external').mkdir()
            (project / 'ios/Pods/fmt').symlink_to(project / 'external')
            with self.assertRaisesRegex(ValueError, 'symlinked Pod'):
                expo.unlock_cached_pod(project, 'fmt')

    def test_unknown_glog_config_fails_without_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            header = root / 'ios/Pods/glog/src/config.h'
            header.parent.mkdir(parents=True)
            original = '#define CUSTOM_GLOG_CONFIG 1\n'
            header.write_text(original)
            with patch.object(expo, 'run') as run, self.assertRaisesRegex(ValueError, 'Unrecognized glog'):
                expo.prepare_glog(Config(root, root), root, root, root)
            run.assert_not_called()
            self.assertEqual(header.read_text(), original)
