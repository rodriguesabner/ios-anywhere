from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ios_linux import cli, godot, signing
from ios_linux.config import Config


class CliTests(unittest.TestCase):
    def test_build_requires_explicit_project(self):
        with self.assertRaises(SystemExit):
            cli.execute(["build", "--output", "new.ipa"])

    def test_build_requires_credentials_for_both_engines(self):
        for engine in ["expo", "godot"]:
            with self.subTest(engine=engine), self.assertRaises(SystemExit):
                cli.execute(
                    [
                        "--engine",
                        engine,
                        "--project",
                        "/tmp/source",
                        "build",
                        "--output",
                        "new.ipa",
                    ]
                )

    def test_doctor_has_no_default_project(self):
        with (
            patch.object(Config, "load", return_value=Config(Path("/tools"), Path("/cache"))),
            patch.object(Config, "doctor") as doctor,
        ):
            cli.execute(["doctor"])
            doctor.assert_called_once_with("expo")

    def test_relative_config_paths_follow_config_location(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "config.json"
            p.write_text('{"toolchain":"tools","cache":"cache"}')
            self.assertEqual(Config.load(p).toolchain, Path(temp) / "tools")

    def test_output_protection(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "app.ipa"
            p.write_bytes(b"preserve")

            with self.assertRaises(ValueError):
                signing.check_output(p)

            self.assertEqual(p.read_bytes(), b"preserve")
            p.unlink()
            p.with_suffix(".verification.json").touch()

            with self.assertRaises(ValueError):
                signing.check_output(p)

    def test_failed_verification_does_not_publish(self):
        import subprocess

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "stage/Payload/Test.app"
            app.mkdir(parents=True)
            (app / "Info.plist").write_text("test")

            def run(args, **kwargs):
                if str(args[1]).endswith("verify-signed.py"):
                    raise subprocess.CalledProcessError(1, args)

            with (
                patch.object(signing, "check_credentials"),
                patch.object(signing.subprocess, "run", side_effect=run),
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    signing.package(
                        Config(root / "tools", root / "cache"),
                        app,
                        root / "out.ipa",
                        root / "credentials.json",
                        root,
                    )

            self.assertFalse((root / "out.ipa").exists())
            self.assertFalse((root / "out.verification.json").exists())

    def test_godot_isolated_identity_and_orientation(self):
        import plistlib

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            text = '[application]\nconfig/name="Portable Game"\n[display]\nwindow/handheld/orientation=1\n'
            (source / "project.godot").write_text(text)
            config = Config(root / "tools", root / "cache")
            job = godot.prepare(config, source, "com.example.game")
            (job / "Game").write_bytes(b"binary")
            (job / "Game.pck").write_bytes(b"GDPCdata")
            app = godot.stage(job)
            info = plistlib.loads((app / "Info.plist").read_bytes())
            self.assertEqual(info["CFBundleIdentifier"], "com.example.game")
            self.assertEqual(info["CFBundleDisplayName"], "Portable Game")

            self.assertEqual(
                info["UISupportedInterfaceOrientations"],
                ["UIInterfaceOrientationPortrait"],
            )

            self.assertEqual((source / "project.godot").read_text(), text)
            self.assertFalse((source / "export_presets.cfg").exists())

    def test_godot_rejects_extensions_and_bad_bundle_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "project.godot").touch()
            config = Config(root / "tools", root / "cache")

            with self.assertRaisesRegex(ValueError, "Bundle ID"):
                godot.prepare(config, source, "../../escape")

            (source / "plugin.gdextension").touch()

            with self.assertRaisesRegex(ValueError, "GDExtensions"):
                godot.prepare(config, source, "com.example.game")
