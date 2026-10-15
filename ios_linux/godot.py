"""Godot PCK export plus the separately installed arm64 engine."""

import hashlib
import json
import plistlib
import re
import shutil
from .config import SCRIPTS, TEMPLATES
from .expo import run
from . import signing


def prepare(config, source, bundle_id):
    if not (source / "project.godot").is_file():
        raise ValueError("A pasta precisa conter project.godot.")

    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+)+", bundle_id):
        raise ValueError("Bundle ID inválido.")

    if any(source.rglob("*.gdextension")) or any(source.rglob("*.cs")):
        raise ValueError("Este engine não inclui suporte a C# ou GDExtensions.")

    key = bundle_id + "-" + hashlib.sha256(str(source).encode()).hexdigest()[:10]
    job = config.cache / "godot" / key

    if source == job or source.is_relative_to(job) or job.is_relative_to(source):
        raise ValueError("A fonte precisa ficar fora da área de build.")

    job.mkdir(parents=True, exist_ok=True)
    project = job / "project"

    if project.exists():
        shutil.rmtree(project)

    shutil.copytree(source, project, ignore=shutil.ignore_patterns(".godot", ".git", "*.log"))
    text = (project / "project.godot").read_text()
    title = re.search(r'^config/name="(.*)"$', text, re.M)
    title = title.group(1) if title else source.name
    presets = project / "export_presets.cfg"

    exclude = re.search(
        r"^exclude_filter=(.*)$", presets.read_text() if presets.exists() else "", re.M
    )

    excluded = exclude.group(1) if exclude else '""'

    presets.write_text(
        '[preset.0]\nname="iOS"\nplatform="iOS"\nrunnable=false\nexport_filter="all_resources"\ninclude_filter=""\nexclude_filter='
        + excluded
        + "\n[preset.0.options]\napplication/bundle_identifier="
        + json.dumps(bundle_id)
        + "\n"
    )

    (job / "identity.json").write_text(json.dumps({"bundle_id": bundle_id, "title": title}))
    return job


def bundle(config, job):
    executable = config.toolchain / "godot/godot"

    run(
        [executable, "--headless", "--path", job / "project", "--editor", "--import"],
        job,
        job / "import.log",
    )

    run(
        [
            executable,
            "--headless",
            "--path",
            job / "project",
            "--export-pack",
            "iOS",
            job / "Game.pck",
        ],
        job,
        job / "export.log",
    )

    with (job / "Game.pck").open("rb") as stream:
        if stream.read(4) != b"GDPC":
            raise ValueError("Godot não produziu um PCK válido.")


def native(config, job):
    tools = config.toolchain
    sdk = tools / "sdks/iPhoneOS18.5.sdk"
    clang = tools / "swift/usr/bin/clang"

    run(
        [
            clang,
            "-target",
            "arm64-apple-ios14.0",
            "-c",
            TEMPLATES / "dummy.cpp",
            "-o",
            job / "dummy.o",
        ],
        job,
        job / "compile-support.log",
    )

    run(
        [
            clang,
            "-target",
            "arm64-apple-ios14.0",
            "-isysroot",
            sdk,
            "-include",
            "stdbool.h",
            "-O2",
            "-c",
            SCRIPTS / "os_version_check.c",
            "-o",
            job / "os_version_check.o",
        ],
        job,
        job / "compile-runtime.log",
    )

    run(
        [
            tools / "darwin-tools/bin/ld64.lld",
            "-arch",
            "arm64",
            "-platform_version",
            "ios",
            "14.0",
            "18.5",
            "-syslibroot",
            sdk,
            "-o",
            job / "Game",
            job / "dummy.o",
            job / "os_version_check.o",
            tools / "godot/libgodot.a",
            tools / "godot/libMoltenVK.a",
            "-lSystem",
            "-lc++",
            "-lc++abi",
            "-lz",
            "-liconv",
            "-ObjC",
        ],
        job,
        job / "link.log",
    )


def stage(job):
    root = job / "stage"

    if root.exists():
        shutil.rmtree(root)

    app = root / "Payload/Game.app"
    app.mkdir(parents=True)

    for name in ["Game", "Game.pck"]:
        shutil.copy2(job / name, app / name)

    (app / "Game").chmod(0o755)
    shutil.copy2(TEMPLATES / "PrivacyInfo.xcprivacy", app / "PrivacyInfo.xcprivacy")
    identity = json.loads((job / "identity.json").read_text())
    text = (job / "project/project.godot").read_text()
    value = re.search(r"^window/handheld/orientation=(\d+)$", text, re.M)

    landscape = [
        "UIInterfaceOrientationLandscapeLeft",
        "UIInterfaceOrientationLandscapeRight",
    ]

    portrait = [
        "UIInterfaceOrientationPortrait",
        "UIInterfaceOrientationPortraitUpsideDown",
    ]

    orientations = {
        0: landscape[:1],
        1: portrait[:1],
        2: landscape[1:],
        3: portrait[1:],
        4: landscape,
        5: portrait,
        6: landscape + portrait,
    }

    orientation = orientations.get(int(value.group(1)) if value else 0, landscape)

    info = dict(
        CFBundleDisplayName=identity["title"],
        CFBundleExecutable="Game",
        CFBundleName="Game",
        CFBundleIdentifier=identity["bundle_id"],
        CFBundlePackageType="APPL",
        CFBundleShortVersionString="1.0",
        CFBundleVersion="1",
        MinimumOSVersion="14.0",
        CFBundleSupportedPlatforms=["iPhoneOS"],
        UIDeviceFamily=[1, 2],
        UIRequiredDeviceCapabilities=["arm64"],
        UILaunchScreen={},
        UIRequiresFullScreen=True,
        UIStatusBarHidden=True,
        CADisableMinimumFrameDurationOnPhone=True,
        UISupportedInterfaceOrientations=orientation,
        **{"UISupportedInterfaceOrientations~ipad": orientation},
    )

    icon = re.search(r'^config/icon="res://([^"\n]+)"$', text, re.M)

    if icon:
        project = (job / "project").resolve()
        path = (project / icon.group(1)).resolve()

        if path.is_relative_to(project) and path.suffix.lower() == ".png" and path.is_file():
            from PIL import Image

            with Image.open(path) as image:
                for size in [120, 180, 76, 152, 167]:
                    image.convert("RGB").resize((size, size), Image.Resampling.LANCZOS).save(
                        app / f"Icon-{size}.png"
                    )

            info["CFBundleIcons"] = {
                "CFBundlePrimaryIcon": {"CFBundleIconFiles": ["Icon-120", "Icon-180"]}
            }

            info["CFBundleIcons~ipad"] = {
                "CFBundlePrimaryIcon": {"CFBundleIconFiles": ["Icon-76", "Icon-152", "Icon-167"]}
            }

    (app / "Info.plist").write_bytes(plistlib.dumps(info))
    return app


def build(config, source, bundle_id, output, credentials):
    signing.check_output(output)
    signing.check_credentials(credentials)
    job = prepare(config, source, bundle_id)
    bundle(config, job)
    native(config, job)
    signing.package(config, stage(job), output, credentials, job)
