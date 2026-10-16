"""Local toolchain and cache paths; never infer them from an app project."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil

SCRIPTS = Path(__file__).parent / "scripts"
TEMPLATES = Path(__file__).parent / "templates"


def default_config():
    root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config").expanduser()
    preferred = root / "ios-anywhere/config.json"
    legacy = root / "ios-linux/config.json"
    # Never migrate or overwrite a user's files, or hide an invalid new config.
    if preferred.exists() or preferred.is_symlink() or not legacy.is_file():
        return preferred
    return legacy


@dataclass(frozen=True)
class Config:
    toolchain: Path
    cache: Path
    llvm_ar: str = "llvm-ar"
    installer: str = "ideviceinstaller"
    installer_lib: str = ""

    @classmethod
    def load(cls, path=None):
        path = (path or default_config()).expanduser().resolve()

        if not path.is_file():
            raise ValueError(f"Configuration not found: {path}. See docs/toolchain.md.")

        data = json.loads(path.read_text())

        def resolve(value):
            p = Path(value).expanduser()
            return (path.parent / p).resolve() if not p.is_absolute() else p.resolve()

        return cls(
            resolve(data["toolchain"]),
            resolve(data["cache"]),
            data.get("llvm_ar", "llvm-ar"),
            data.get("installer", "ideviceinstaller"),
            data.get("installer_lib", ""),
        )

    def env(self):
        tools = self.toolchain

        return dict(
            os.environ,
            IOS_LINUX_TOOLCHAIN=str(tools),
            IOS_LINUX_SIGNING_MODULE=str(tools / "signing/node_modules/zsign-wasm"),
            PYTHONOPTIMIZE="0",
        )

    def doctor(self, engine):
        required = [
            "swift/usr/bin/clang",
            "darwin-tools/bin/ld64.lld",
            "signing/node_modules/zsign-wasm/package.json",
        ]

        if engine == "expo":
            required += [
                "swift/usr/bin/swiftc",
                "ruby/usr/bin/ruby3.2",
                "gems/bin/pod",
                "sdks/iPhoneOS26.4.sdk/SDKSettings.json",
                "sdks/iPhoneOS26.5.sdk/SDKSettings.json",
                "darwin-resource/iphoneos/Cxx.swiftmodule/arm64-apple-ios.swiftinterface",
                "darwin-resource/shims",
                "apple-macros/OpenAppleMacrosServer",
                "host-macros/ExpoModulesMacros-tool",
                "os_version_check.o",
                "cxx-runtime/compat-markers.o",
            ]
        else:
            required += [
                "godot/godot",
                "godot/libgodot.a",
                "godot/libMoltenVK.a",
                "sdks/iPhoneOS18.5.sdk/SDKSettings.json",
            ]

        errors = [
            f"Missing: {self.toolchain / name}"
            for name in required
            if not (self.toolchain / name).exists()
        ]

        for command in ["node", "openssl"] + (["npm", self.llvm_ar] if engine == "expo" else []):
            if not shutil.which(command):
                errors.append(f"Command not found: {command}")

        if errors:
            raise ValueError("\n".join(errors))

        print(f"OK: {engine} tools available. Toolchain: {self.toolchain}")
