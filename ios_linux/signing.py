"""Shared signing and atomic IPA publication for both engines."""

import json
from pathlib import Path
import subprocess
import tempfile
import zipfile
from .config import SCRIPTS


def check_output(output):
    if (
        output.suffix.lower() != ".ipa"
        or output.exists()
        or output.with_suffix(".verification.json").exists()
    ):
        raise ValueError("Choose a new .ipa --output with no existing file or verification report.")


def check_credentials(path):
    data = json.loads(path.read_text()).get("ios")

    if not data:
        raise ValueError("Credentials must contain an ios section.")

    entries = [data] if "distributionCertificate" in data else list(data.values())

    if not entries:
        raise ValueError("Empty iOS credentials.")

    for entry in entries:
        cert = entry["distributionCertificate"]

        if "password" not in cert:
            raise ValueError("Certificate password is missing.")

        for value in [cert["path"], entry["provisioningProfilePath"]]:
            if not (path.parent / value).is_file():
                raise ValueError("Signing file not found; check credentials.json.")


def check_bundle_profiles(app, credentials):
    """Require one exact profile per executable bundle before invoking the signer."""
    import plistlib
    data = json.loads(credentials.read_text())["ios"]
    entries = [data] if "distributionCertificate" in data else list(data.values())
    certificates = {(credentials.parent / e["distributionCertificate"]["path"]).read_bytes()
                    for e in entries}
    passwords = {e["distributionCertificate"]["password"] for e in entries}
    if len(certificates) != 1 or len(passwords) != 1:
        raise ValueError("Multi-target signing requires the same distribution certificate for all targets.")
    profiles = {}
    for entry in entries:
        decoded = subprocess.run(
            ["openssl", "cms", "-verify", "-inform", "DER", "-noverify",
             "-in", str(credentials.parent / entry["provisioningProfilePath"])],
            capture_output=True, check=True)
        profile = plistlib.loads(decoded.stdout)
        identity = profile["Entitlements"]["application-identifier"]
        bundle_id = identity.split(".", 1)[1]
        if bundle_id in profiles:
            raise ValueError("Duplicate provisioning profiles for a bundle identifier.")
        profiles[bundle_id] = profile
    bundles = [app, *sorted(app.glob("PlugIns/*.appex"))]
    for bundle in bundles:
        info = plistlib.loads((bundle / "Info.plist").read_bytes())
        if info["CFBundleIdentifier"] not in profiles:
            raise ValueError("Missing exact provisioning profile for target " + bundle.name)
        requested = bundle / "ios-anywhere-entitlements.plist"
        if requested.exists():
            entitlements = plistlib.loads(requested.read_bytes())
            allowed = profiles[info["CFBundleIdentifier"]]["Entitlements"]
            for key, value in entitlements.items():
                actual = allowed.get(key)
                if key == "aps-environment":
                    # Distribution export uses the environment authorized by its profile,
                    # even when Expo prebuild generated development entitlements.
                    valid = value in ("development", "production") and actual in ("development", "production")
                elif isinstance(value, list):
                    valid = isinstance(actual, list) and set(value).issubset(actual)
                else:
                    valid = actual == value
                if not valid:
                    raise ValueError("Provisioning profile does not authorize entitlement " + key + " for " + bundle.name)
    # Validation-only metadata must not be distributed inside the application.
    for bundle in bundles:
        (bundle / "ios-anywhere-entitlements.plist").unlink(missing_ok=True)


def package(config, app, output, credentials, log_dir):
    check_output(output)
    check_credentials(credentials)
    check_bundle_profiles(app, credentials)
    env = dict(config.env(), IOS_LINUX_CREDENTIALS=str(credentials), IOS_LINUX_APP=str(app))

    with (log_dir / "sign.log").open("w") as log:
        subprocess.run(
            ["node", str(SCRIPTS / "sign-app.cjs")],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )

    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output.parent, prefix="ios-linux-") as temp:
        candidate = Path(temp) / output.name

        with zipfile.ZipFile(candidate, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(app.parent.parent.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(app.parent.parent))

        with (log_dir / "verify.log").open("w") as log:
            subprocess.run(
                ["python3", str(SCRIPTS / "verify-signed.py"), str(candidate)],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )

        # Recheck after expensive signing so a newly created output is never replaced.
        check_output(output)
        import os

        os.link(candidate, output)

        try:
            os.link(
                candidate.with_suffix(".verification.json"),
                output.with_suffix(".verification.json"),
            )
        except Exception:
            output.unlink()
            raise

    print(f"IPA signed and verified: {output}")
