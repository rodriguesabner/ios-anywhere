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


def package(config, app, output, credentials, log_dir):
    check_output(output)
    check_credentials(credentials)
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


def check_identity(credentials, bundle_id):
    """Check profile identity only; final signature verification remains mandatory."""
    import plistlib
    check_credentials(credentials)
    data = json.loads(credentials.read_text())['ios']
    entries = [data] if 'distributionCertificate' in data else list(data.values())
    identities = []
    for entry in entries:
        profile = credentials.parent / entry['provisioningProfilePath']
        result = subprocess.run(['openssl', 'cms', '-verify', '-inform', 'DER', '-noverify',
                                 '-in', str(profile)], capture_output=True)
        if result.returncode:
            raise ValueError(f'Cannot decode provisioning profile: {profile.name}')
        try:
            identity = plistlib.loads(result.stdout)['Entitlements']['application-identifier']
            identifier = identity.split('.', 1)[1]
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
            raise ValueError(f'Invalid profile application identifier: {profile.name}') from error
        identities.append(identifier)
    if bundle_id not in identities:
        raise ValueError(f'Bundle ID {bundle_id!r} does not match the provisioning profile(s): '
                         f'{", ".join(identities)}. Set ios.bundleIdentifier in the Expo config '
                         '(or --bundle-id for Godot), or choose credentials for this app. '
                         'An exact app profile is required by this signing pipeline.')
