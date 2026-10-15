"""Explicit projects, external toolchain, isolated build caches."""

import argparse
import fcntl
from pathlib import Path
import os
import subprocess
import sys
from . import __version__
from .config import Config, SCRIPTS
from . import expo, godot, signing


def parser():
    p = argparse.ArgumentParser(
        description="Builds iOS locais no Linux: Expo e Godot (experimental)."
    )

    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--config", type=Path, help="Configuração local da toolchain")
    p.add_argument("--engine", choices=["expo", "godot"], default="expo")
    p.add_argument("--project", type=Path, help="Fonte do app; nunca editada pelo CLI")

    p.add_argument(
        "--credentials",
        type=Path,
        help="credentials.json com certificado e provisioning deste app",
    )

    p.add_argument("--bundle-id", help="Identidade do app Godot; Expo usa app.json/app.config")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Verifica ferramentas sem exigir projeto")
    sub.add_parser("bundle", help="Gera recursos JS/Hermes ou PCK sem assinar")
    build = sub.add_parser("build", help="Prepara, compila, assina e verifica")
    build.add_argument("--output", type=Path, required=True)
    install = sub.add_parser("install", help="Instala um IPA existente")
    install.add_argument("ipa", type=Path)
    install.add_argument("--udid", required=True)
    verify = sub.add_parser("verify", help="Verifica integridade e assinatura local do IPA")
    verify.add_argument("ipa", type=Path)
    return p


def execute(argv=None):
    p = parser()
    args = p.parse_args(argv)

    if args.command in ("build", "bundle") and not args.project:
        p.error("--project é obrigatório.")

    if args.command == "build" and not args.credentials:
        p.error("--credentials é obrigatório para ambos os motores.")

    if args.command in ("build", "bundle") and args.engine == "godot" and not args.bundle_id:
        p.error("--bundle-id é obrigatório para Godot.")

    if args.bundle_id and args.engine != "godot":
        p.error("Expo usa a identidade configurada no projeto.")

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
            raise ValueError("IPA não encontrado.")

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
            raise ValueError("O projeto precisa ficar fora da toolchain e do cache.")

    config.cache.mkdir(parents=True, exist_ok=True)

    with (config.cache / "build.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Outro build ios-linux está em execução neste cache.")

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
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrompido; confira os logs no cache.", file=sys.stderr)
        return 130
