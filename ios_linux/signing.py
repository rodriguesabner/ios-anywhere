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
        raise ValueError("Escolha um --output .ipa novo, sem arquivo ou relatório existente.")


def check_credentials(path):
    data = json.loads(path.read_text()).get("ios")

    if not data:
        raise ValueError("Credenciais precisam conter ios.")

    entries = [data] if "distributionCertificate" in data else list(data.values())

    if not entries:
        raise ValueError("Credenciais iOS vazias.")

    for entry in entries:
        cert = entry["distributionCertificate"]

        if "password" not in cert:
            raise ValueError("Senha do certificado ausente.")

        for value in [cert["path"], entry["provisioningProfilePath"]]:
            if not (path.parent / value).is_file():
                raise ValueError("Arquivo de assinatura ausente; confira credentials.json.")


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

    print(f"IPA assinado e verificado: {output}")
