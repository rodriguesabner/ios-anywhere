"""SDK-free CI orchestration tests; no real signing or toolchain execution."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ios_linux.config import Config

spec = importlib.util.spec_from_file_location("ci_build", Path(__file__).resolve().parents[1] / "scripts/ci_build.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class CIBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.credentials = self.root / "credentials.json"
        self.credentials.write_text(json.dumps({"ios": {
            "distributionCertificate": {"path": "cert.p12", "password": "PRIVATE_TEST_VALUE"},
            "provisioningProfilePath": "profile.mobileprovision"}}))
        (self.root / "cert.p12").touch()
        (self.root / "profile.mobileprovision").touch()
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps({"toolchain": str(self.tools), "cache": str(self.root / "keep-cache")}))
        self.config = Config.load(self.config_path)

    def test_rejects_checkout_and_symlink_to_checkout(self):
        with self.assertRaises(ValueError):
            ci.outside_checkout(ci.ROOT / "config.example.json")
        link = self.root / "config-link"
        link.symlink_to(ci.ROOT / "config.example.json")
        with self.assertRaises(ValueError):
            ci.outside_checkout(link)

    def test_rejects_signing_file_symlink_into_checkout(self):
        (self.root / "cert.p12").unlink()
        (self.root / "cert.p12").symlink_to(ci.ROOT / "README.md")
        with patch.object(Config, "doctor"), patch.object(ci.os, "access", return_value=True):
            with self.assertRaises(ValueError):
                ci.preflight("godot", self.config_path, self.credentials, "com.example.test")

    def test_preflight_rejects_bad_identity_and_host(self):
        for identity in ["", "bad id", "$(echo nope)"]:
            with self.assertRaises(ValueError):
                ci.preflight("godot", self.config_path, self.credentials, identity)
        with patch.object(ci.platform, "system", return_value="Darwin"):
            with self.assertRaises(ValueError):
                ci.preflight("godot", self.config_path, self.credentials, "com.example.test")

    def test_preflight_checks_backend_tools_and_external_credentials(self):
        with patch.object(Config, "doctor") as doctor, patch.object(ci.os, "access", return_value=True):
            config, credentials = ci.preflight("godot", self.config_path, self.credentials, "com.example.test")
            doctor.assert_called_once_with("godot")
            self.assertEqual(config, self.config)
            self.assertEqual(credentials, self.credentials)
        with patch.object(Config, "doctor"), patch.object(ci.os, "access", return_value=False):
            with self.assertRaises(ValueError):
                ci.preflight("godot", self.config_path, self.credentials, "com.example.test")

    def run_fake_build(self, engine, returncode=0, create_output=True):
        output = self.root / "artifacts/app.ipa"
        captured = {}
        def fake_run(command, **kwargs):
            self.assertNotIn("PRIVATE_TEST_VALUE", " ".join(command))
            for variable in ["npm_config_cache", "XDG_CACHE_HOME", "CP_HOME_DIR", "CP_CACHE_DIR"]:
                self.assertTrue(Path(kwargs["env"][variable]).is_relative_to(Path(command[command.index("--project") + 1]).parent))
            project = Path(command[command.index("--project") + 1])
            config_path = Path(command[command.index("--config") + 1])
            captured["work"] = project.parent
            local = json.loads(config_path.read_text())
            self.assertEqual(local["toolchain"], str(self.tools))
            self.assertNotEqual(local["cache"], str(self.config.cache))
            if engine == "expo":
                self.assertEqual(json.loads((project / "app.json").read_text())["expo"]["ios"]["bundleIdentifier"], "com.example.ci")
                self.assertNotIn("--bundle-id", command)
            else:
                self.assertEqual(command[command.index("--bundle-id") + 1], "com.example.ci")
            self.assertEqual(command[-3:], ["build", "--output", str(output)])
            if create_output:
                output.parent.mkdir(parents=True)
                output.touch()
                output.with_suffix(".verification.json").write_text("{}")
            return subprocess.CompletedProcess(command, returncode)
        with patch.object(ci, "preflight", return_value=(self.config, self.credentials)), patch.object(ci.subprocess, "run", side_effect=fake_run):
            if returncode or not create_output:
                with self.assertRaises(ValueError):
                    ci.build_example(engine, self.config_path, self.credentials, "com.example.ci", output)
            else:
                ci.build_example(engine, self.config_path, self.credentials, "com.example.ci", output)
        self.assertFalse(captured["work"].exists())
        self.assertTrue(self.credentials.is_file())
        self.assertTrue(self.tools.is_dir())

    def test_godot_command_and_cleanup(self):
        self.run_fake_build("godot")

    def test_expo_identity_and_cleanup(self):
        original = (ci.ROOT / "examples/expo-counter/app.json").read_bytes()
        self.run_fake_build("expo")
        self.assertEqual((ci.ROOT / "examples/expo-counter/app.json").read_bytes(), original)

    def test_cleanup_on_build_failure(self):
        self.run_fake_build("godot", returncode=1, create_output=False)

    def test_rejects_missing_artifacts(self):
        self.run_fake_build("godot", create_output=False)

    def test_refuses_existing_output_before_preflight(self):
        output = self.root / "existing.ipa"
        output.touch()
        with patch.object(ci, "preflight") as preflight:
            with self.assertRaises(ValueError):
                ci.build_example("godot", self.config_path, self.credentials, "com.example.ci", output)
            preflight.assert_not_called()

    def test_errors_never_echo_credential_content(self):
        env = {"IOS_ANYWHERE_CONFIG": str(self.config_path), "IOS_ANYWHERE_CREDENTIALS": str(self.credentials), "IOS_ANYWHERE_BUNDLE_ID": "com.example.ci"}
        import io
        with patch.dict(ci.os.environ, env), patch.object(ci.sys, "argv", ["ci_build.py", "--engine", "godot", "--output", str(self.root / "app.ipa")]), patch.object(ci, "build_example", side_effect=ValueError("PRIVATE_TEST_VALUE")), patch.object(ci.sys, "stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(ci.main(), 1)
            self.assertNotIn("PRIVATE_TEST_VALUE", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
