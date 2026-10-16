"""Interactive Apple provisioning, with credentials stored outside the project."""

import json
import os
from pathlib import Path
import shutil
import subprocess

from . import devices
from .config import SCRIPTS

DEPENDENCIES = {'@expo/apple-utils': '2.2.1', 'prompts': '2.4.2'}


def setup(config, output):
    from .interactive import ask
    output = output.expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Choose a new signing folder; existing files are preserved.')
    env = config.env()
    for tool in ('node', 'npm', 'openssl'):
        if not shutil.which(tool, path=env['PATH']):
            raise ValueError(f'{tool} is required. Run toolchain setup first.')
    root = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share').expanduser()
    helper = root / 'ios-anywhere/apple-profile-helper'
    ready = all((helper / 'node_modules' / name / 'package.json').is_file()
                and json.loads((helper / 'node_modules' / name / 'package.json').read_text())['version'] == version
                for name, version in DEPENDENCIES.items())
    if not ready:
        print('Signing needs a one-time download of @expo/apple-utils and prompts.\n'
              'These helpers talk to your Apple Developer account; this does not build on EAS.\n'
              'Apple account changes are confirmed separately. Choosing No stops signing setup.')
        if not ask('confirm', 'Install Apple provisioning helpers from npm (@expo/apple-utils and prompts)?', default=False):
            return
        helper.mkdir(parents=True, exist_ok=True)
        subprocess.run(['npm', 'install', '--prefix', str(helper), '--ignore-scripts', '--save-exact',
                        *[f'{name}@{version}' for name, version in DEPENDENCIES.items()]], env=env, check=True)
    subprocess.run(['node', str(SCRIPTS / 'setup-signing.cjs'), str(helper), str(output)], env=env, check=True)
    result = output / 'device.json'
    if result.is_file():
        device = json.loads(result.read_text())
        devices.save(device['name'], device['udid'])
        print(f"Saved iPhone: {device['name']}. Connect, unlock, and trust this computer before installing.")
