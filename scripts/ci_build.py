"""Build trusted bundled examples with an already provisioned Linux toolchain.

No toolchain downloads, credential provisioning, device installation, or Apple submission.
Project dependencies may be downloaded and executed during a build.
"""
import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

from ios_linux.config import Config
from ios_linux.signing import check_credentials, check_output

ROOT = Path(__file__).resolve().parents[1]


def outside_checkout(path):
    path = Path(path).expanduser().resolve(strict=True)
    if path.is_relative_to(ROOT):
        raise ValueError("Configuration and signing files must be outside the checkout.")
    return path


def preflight(engine, config_path, credentials_path, bundle_id):
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("The CI build requires Linux x86_64.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+)+", bundle_id):
        raise ValueError("Supply the bundle ID covered by your provisioning profile.")
    config = Config.load(outside_checkout(config_path))
    outside_checkout(config.toolchain)
    with redirect_stdout(io.StringIO()):
        config.doctor(engine)
    executables = ["swift/usr/bin/clang", "darwin-tools/bin/ld64.lld"]
    executables += (["swift/usr/bin/swiftc", "ruby/usr/bin/ruby3.2", "gems/bin/pod",
                     "apple-macros/OpenAppleMacrosServer", "host-macros/ExpoModulesMacros-tool"]
                    if engine == "expo" else ["godot/godot"])
    if any(not os.access(config.toolchain / name, os.X_OK) for name in executables):
        raise ValueError("A required toolchain executable is not executable.")
    credentials = outside_checkout(credentials_path)
    check_credentials(credentials)
    data = json.loads(credentials.read_text())["ios"]
    entries = [data] if "distributionCertificate" in data else list(data.values())
    for entry in entries:
        for value in [entry["distributionCertificate"]["path"], entry["provisioningProfilePath"]]:
            outside_checkout(credentials.parent / value)
    return config, credentials


def build_example(engine, config_path, credentials_path, bundle_id, output):
    output = Path(output).resolve()
    check_output(output)
    config, credentials = preflight(engine, config_path, credentials_path, bundle_id)
    # Own only this fresh directory. Never delete the operator's configured cache,
    # toolchain, or credentials, including on a failed build.
    with tempfile.TemporaryDirectory(prefix="ios-anywhere-ci-") as temp:
        work = Path(temp)
        project = work / "project"
        shutil.copytree(ROOT / "examples" / f"{engine}-counter", project,
                        ignore=shutil.ignore_patterns("node_modules", ".expo", ".godot"))
        if engine == "expo":
            app = project / "app.json"
            data = json.loads(app.read_text())
            data["expo"]["ios"]["bundleIdentifier"] = bundle_id
            app.write_text(json.dumps(data))
        local_config = work / "config.json"
        local_config.write_text(json.dumps({"toolchain": str(config.toolchain),
                                            "cache": str(work / "cache"),
                                            "llvm_ar": config.llvm_ar}))
        command = [sys.executable, "-m", "ios_linux", "--config", str(local_config),
                   "--engine", engine, "--project", str(project),
                   "--credentials", str(credentials)]
        if engine == "godot":
            command += ["--bundle-id", bundle_id]
        command += ["build", "--output", str(output)]
        print(f"Building {engine}; private build logs are temporary and will not be uploaded.", flush=True)
        # Build/project hooks and signer output may contain private information.
        # Do not stream logs or include CalledProcessError output in Actions logs.
        with (work / "build.log").open("w") as log:
            env = dict(os.environ,
                       npm_config_cache=str(work / "npm-cache"),
                       XDG_CACHE_HOME=str(work / "xdg-cache"),
                       CP_HOME_DIR=str(work / "cocoapods-home"),
                       CP_CACHE_DIR=str(work / "cocoapods-cache"))
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
        if result.returncode:
            raise ValueError("Build failed. Reproduce privately on the prepared runner to inspect logs.")
        if not output.is_file() or not output.with_suffix(".verification.json").is_file():
            raise ValueError("Build did not produce an IPA and local verification report.")
    print("IPA built and locally verified. No device test or Apple upload performed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["expo", "godot"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    required = ["IOS_ANYWHERE_CONFIG", "IOS_ANYWHERE_CREDENTIALS", "IOS_ANYWHERE_BUNDLE_ID"]
    if any(not os.environ.get(name) for name in required):
        parser.error("Set IOS_ANYWHERE_CONFIG, IOS_ANYWHERE_CREDENTIALS, and IOS_ANYWHERE_BUNDLE_ID.")
    try:
        build_example(args.engine, *(os.environ[name] for name in required), args.output)
    except (ValueError, KeyError, OSError, TypeError):
        # Malformed credential/config exceptions can contain user-controlled values.
        print("CI build failed. Check external config, tools, credentials, bundle ID, and available disk. "
              "See docs/ci.md for private diagnosis.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
