"""Explicit projects, external toolchain, isolated build caches."""

import argparse
import fcntl
from pathlib import Path
import os
import subprocess
import shutil
import sys
from . import __version__
from .config import Config, SCRIPTS
from . import expo, godot, signing


def parser():
    p = argparse.ArgumentParser(
        description="Local iOS builds on Linux: Expo and Godot (experimental)."
    )

    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--config", type=Path, help="Local toolchain configuration")
    p.add_argument("--engine", choices=["expo", "godot"])
    p.add_argument("--project", type=Path, help="App source; never modified by the CLI")

    p.add_argument(
        "--credentials",
        type=Path,
        help="credentials.json with this app's certificate and provisioning profile",
    )

    p.add_argument("--bundle-id", help="Godot app identity; Expo uses app.json/app.config")
    sub = p.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup", help="Install an Expo or Godot toolchain interactively (Linux x86_64)")
    setup.add_argument("--engine", dest="setup_engine", choices=["expo", "godot"], help="Godot by default; Expo requires Ubuntu 24.04")
    setup.add_argument("--toolchain", type=Path, help="New toolchain directory; existing directories are preserved")
    setup.add_argument("--sdk-source", choices=["local", "mirror"], help="Import a local SDK or use the unofficial pinned mirror")
    setup.add_argument("--sdk", type=Path, help="Godot: iPhoneOS18.5.sdk; Expo: parent folder containing iPhoneOS26.4.sdk and iPhoneOS26.5.sdk")
    setup.add_argument("--yes", action="store_true", help="Accept tool downloads and missing apt packages; requires --sdk-source")
    sub.add_parser("doctor", help="Check tools without requiring a project")
    sub.add_parser("bundle", help="Generate JS/Hermes or PCK resources without signing")
    build = sub.add_parser("build", help="Prepare, compile, sign, and verify")
    build.add_argument("--output", type=Path, required=True)
    install = sub.add_parser("install", help="Install an existing IPA")
    install.add_argument("ipa", type=Path)
    install.add_argument("--udid", required=True)
    verify = sub.add_parser("verify", help="Verify IPA integrity and signature locally")
    verify.add_argument("ipa", type=Path)
    return p


def execute(argv=None):
    p = parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv and sys.stdin.isatty() and sys.stdout.isatty():
        from .interactive import arguments
        argv = arguments()
        if argv is None:
            return
    args = p.parse_args(argv)

    if args.command == "setup":
        from .setup import setup
        setup(args)
        return

    args.engine = args.engine or "expo"

    if args.command in ("build", "bundle") and not args.project:
        p.error("--project is required.")

    if args.command == "build" and not args.credentials:
        p.error("--credentials is required for both engines.")

    if args.command in ("build", "bundle") and args.engine == "godot" and not args.bundle_id:
        p.error("--bundle-id is required for Godot.")

    if args.bundle_id and args.engine != "godot":
        p.error("Expo uses the identity configured in the project.")

    if args.command == "verify":
        subprocess.run(
            ["python3", str(SCRIPTS / "verify-signed.py"), str(args.ipa.resolve())],
            env=dict(os.environ, PYTHONOPTIMIZE="0"),
            check=True,
        )

        return

    config = Config.load(args.config)

    if args.command == "install":
        if not args.ipa.is_file():
            raise ValueError("IPA not found.")

        if not shutil.which(config.installer):
            raise ValueError(
                f"iPhone installer not found: {config.installer}. "
                "On Ubuntu/Debian run: sudo apt-get install ideviceinstaller libimobiledevice-utils usbmuxd. "
                "Then connect and unlock the iPhone and run idevicepair pair."
            )

        env = dict(os.environ)

        if config.installer_lib:
            env["LD_LIBRARY_PATH"] = config.installer_lib

        subprocess.run(
            [config.installer, "-u", args.udid, "-i", str(args.ipa.resolve())],
            env=env,
            check=True,
        )

        return

    if args.command == "build":
        signing.check_output(args.output.resolve())
        signing.check_credentials(args.credentials.resolve())

    config.doctor(args.engine)

    if args.command == "doctor":
        return

    source = args.project.resolve()

    # Toolchain and cache are ownership boundaries; never treat either as a source tree.
    for managed in [config.cache, config.toolchain]:
        if source == managed or source.is_relative_to(managed) or managed.is_relative_to(source):
            raise ValueError("The project must be outside the toolchain and cache directories.")

    config.cache.mkdir(parents=True, exist_ok=True)

    with (config.cache / "build.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another ios-anywhere build is running in this cache.")

        if args.command == "build":
            if args.engine == "expo":
                expo.build(config, source, args.output.resolve(), args.credentials.resolve())
            else:
                godot.build(
                    config,
                    source,
                    args.bundle_id,
                    args.output.resolve(),
                    args.credentials.resolve(),
                )
        else:
            if args.engine == "expo":
                expo.bundle(config, expo.prepare(config, source))
            else:
                godot.bundle(config, godot.prepare(config, source, args.bundle_id))


def main(argv=None):
    try:
        execute(argv)
        return 0
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted; check the logs in the cache.", file=sys.stderr)
        return 130
