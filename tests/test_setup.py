import hashlib
import io
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch
import zipfile

from ios_linux import cli, setup


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config.json"
        self.tools = self.root / "tools"

    def args(self, *extra):
        return cli.parser().parse_args([
            "--config", str(self.config), "setup", "--toolchain", str(self.tools),
            "--sdk-source", "mirror", "--yes", *extra,
        ])

    def test_setup_dispatches_before_loading_config(self):
        with patch.object(setup, "setup") as action, patch.object(cli.Config, "load") as load:
            cli.execute(["setup", "--engine", "godot"])
            action.assert_called_once()
            load.assert_not_called()

    def test_expo_does_not_silently_install_godot(self):
        from ios_linux import setup_expo
        with patch.object(setup_expo, "check_host", side_effect=ValueError("Unsupported Expo host")), patch.object(setup, "install_tools") as godot:
            with self.assertRaisesRegex(ValueError, "Unsupported Expo host"):
                setup.setup(self.args("--engine", "expo"))
            godot.assert_not_called()

    def test_preserves_existing_config_and_dangling_toolchain(self):
        self.config.write_text("keep")
        with self.assertRaisesRegex(ValueError, "Preserving existing"):
            setup.setup(self.args())
        self.assertEqual(self.config.read_text(), "keep")
        self.config.unlink()
        self.tools.symlink_to(self.root / "absent")
        with self.assertRaisesRegex(ValueError, "Preserving existing"):
            setup.setup(self.args())
        self.assertTrue(self.tools.is_symlink())

    def test_low_disk_stops_before_downloads_or_system_changes(self):
        with patch.object(setup.shutil, "disk_usage") as usage, patch.object(setup, "run") as run:
            usage.return_value.free = 1024
            with self.assertRaisesRegex(ValueError, "8 GiB"):
                setup.setup(self.args())
            run.assert_not_called()
        self.assertFalse(self.tools.exists())
        self.assertFalse(self.config.exists())

    def test_setup_installs_missing_device_tools(self):
        device_tools = {"ideviceinstaller", "idevicepair", "usbmuxd"}
        with patch.object(setup, "check_space"), \
             patch.object(setup.shutil, "which", side_effect=lambda name: None if name in device_tools else "/usr/bin/" + name), \
             patch.object(setup, "run", side_effect=[None, RuntimeError("stop after apt")]) as run:
            with self.assertRaisesRegex(RuntimeError, "stop after apt"):
                setup.setup(self.args())
        command = run.call_args.args[0]
        for package in ("ideviceinstaller", "libimobiledevice-utils", "usbmuxd"):
            self.assertIn(package, command)
        self.assertIn("install", command)

    def test_download_cache_and_corrupt_download(self):
        data = b"verified release"
        digest = hashlib.sha256(data).hexdigest()
        with patch.dict(setup.DOWNLOADS, {"test": ("https://example.com/release.zip", digest)}):
            target = self.root / "release.zip"
            target.write_bytes(data)
            with patch.object(setup, "run") as run:
                self.assertEqual(setup.download("test", self.root), target)
                run.assert_not_called()
            target.write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                setup.download("test", self.root)
            target.unlink()

            def fake_download(command):
                self.assertIn("--retry-all-errors", command)
                self.assertEqual(command[command.index("--continue-at") + 1], "-")
                Path(command[command.index("--output") + 1]).write_bytes(b"bad network payload")

            with patch.object(setup, "run", side_effect=fake_download):
                with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                    setup.download("test", self.root)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_name(target.name + ".part").exists())

    def test_completed_partial_download_is_reused(self):
        data = b"complete"
        with patch.dict(setup.DOWNLOADS, {"test": ("https://example.com/release.zip", hashlib.sha256(data).hexdigest())}):
            (self.root / "release.zip.part").write_bytes(data)
            with patch.object(setup, "run") as run:
                self.assertEqual(setup.download("test", self.root).read_bytes(), data)
                run.assert_not_called()

    def sdk(self):
        sdk = self.root / "source-sdk"
        for name in ["usr/lib/libSystem.tbd", "usr/include/stdio.h"]:
            path = sdk / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        (sdk / "System/Library/Frameworks").mkdir(parents=True)
        (sdk / "SDKSettings.json").write_text('{"Version":"18.5"}')
        return sdk

    def test_local_sdk_rejects_wrong_version_and_external_links(self):
        sdk = self.sdk()
        setup.validate_sdk(sdk)
        (sdk / "escape").symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, "outside"):
            setup.validate_sdk(sdk)
        (sdk / "escape").unlink()
        (sdk / "SDKSettings.json").write_text('{"Version":"26.5"}')
        with self.assertRaisesRegex(ValueError, "18.5"):
            setup.validate_sdk(sdk)

    def test_selected_zip_member_never_uses_archive_destination(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../../escape", b"sample")
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as archive:
            setup.extract_member(archive, "../../escape", self.root / "fixed-file")
        self.assertEqual((self.root / "fixed-file").read_bytes(), b"sample")
        self.assertEqual(list(self.root.iterdir()), [self.root / "fixed-file"])

    def test_install_selects_release_device_libraries(self):
        linker = self.root / "linker.tar.gz"
        with tarfile.open(linker, "w:gz") as archive:
            info = tarfile.TarInfo("bin/ld64.lld")
            info.size, info.mode = 6, 0o755
            archive.addfile(info, io.BytesIO(b"linker"))
        editor = self.root / "editor.zip"
        with zipfile.ZipFile(editor, "w") as archive:
            archive.writestr("Godot_v4.5.1-stable_linux.x86_64", b"editor")
        ios = io.BytesIO()
        with zipfile.ZipFile(ios, "w") as archive:
            archive.writestr("libgodot.ios.release.xcframework/ios-arm64/libgodot.a", b"release")
            archive.writestr("libgodot.ios.debug.xcframework/ios-arm64/libgodot.a", b"debug")
            archive.writestr("libgodot.ios.release.xcframework/ios-arm64_x86_64-simulator/libgodot.a", b"simulator")
            archive.writestr("MoltenVK.xcframework/ios-arm64/libMoltenVK.a", b"vulkan")
        templates = self.root / "templates.tpz"
        with zipfile.ZipFile(templates, "w") as archive:
            archive.writestr("templates/ios.zip", ios.getvalue())
        self.tools.mkdir()
        with patch.object(setup, "download", side_effect=[linker, editor, templates]), \
             patch.object(setup.shutil, "which", return_value="/usr/bin/clang-18"):
            setup.install_tools(self.tools, self.root)
        self.assertEqual((self.tools / "godot/libgodot.a").read_bytes(), b"release")
        self.assertEqual((self.tools / "godot/libMoltenVK.a").read_bytes(), b"vulkan")
        self.assertEqual((self.tools / "darwin-tools/bin/ld64.lld").read_bytes(), b"linker")
        self.assertFalse((self.tools / "ios.zip").exists())

    def test_linker_archive_cannot_escape_staging(self):
        malicious = self.root / "bad.tar"
        with tarfile.open(malicious, "w") as archive:
            info = tarfile.TarInfo("../../../escape")
            info.size = 3
            archive.addfile(info, io.BytesIO(b"bad"))
        self.tools.mkdir()
        with patch.object(setup, "download", return_value=malicious), \
             patch.object(setup.shutil, "which", return_value="/usr/bin/clang-18"):
            with self.assertRaises(tarfile.FilterError):
                setup.install_tools(self.tools, self.root)
        self.assertFalse((self.root / "escape").exists())

    def test_publish_only_after_successful_smoke_test(self):
        for fail in (True, False):
            with self.subTest(fail=fail), patch.object(setup, "check_space"), \
                 patch.object(setup.shutil, "which", return_value="/usr/bin/tool"), \
                 patch.object(setup, "install_tools"), patch.object(setup, "install_sdk"), \
                 patch.object(setup, "run"), patch.object(setup, "smoke_test", side_effect=ValueError("link failed") if fail else None):
                if fail:
                    with self.assertRaisesRegex(ValueError, "link failed"):
                        setup.setup(self.args())
                    self.assertFalse(self.config.exists())
                    self.assertFalse(self.tools.exists())
                    self.assertFalse(list(self.root.glob(".tools-setup-*")))
                else:
                    setup.setup(self.args())
                    self.assertTrue((self.tools / "setup-manifest.json").is_file())
                    self.assertEqual(json.loads(self.config.read_text())["toolchain"], str(self.tools))


if __name__ == "__main__":
    unittest.main()
