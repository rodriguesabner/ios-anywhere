"""Local device names; saving here does not register a device with Apple."""

import json
import os
from pathlib import Path
import re
import plistlib
import subprocess
import zipfile
import tempfile


def validate_udid(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{16}|[0-9a-fA-F]{40})', value):
        raise ValueError('Enter an iPhone UDID: 8-16 hexadecimal digits or 40 hexadecimal digits.')
    return value.upper()


def store_path():
    root = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config').expanduser()
    return root / 'ios-anywhere/devices/saved.json'


def load():
    path = store_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f'Invalid device list: {path}')
    for device in data:
        if not isinstance(device, dict) or not isinstance(device.get('name'), str) or not device['name'].strip():
            raise ValueError(f'Invalid device entry: {path}')
        device['udid'] = validate_udid(device.get('udid', ''))
    return data


def save(name, udid):
    udid = validate_udid(udid)
    if not name.strip():
        raise ValueError('Enter a device name.')
    entries = [d for d in load() if d['udid'] != udid]
    entries.append({'name': name.strip(), 'udid': udid})
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as output:
        temp = Path(output.name)
        try:
            json.dump(entries, output, indent=2)
            output.flush()
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def select():
    from .interactive import ask, choose
    entries = load()
    selected = choose('iPhone', [(f"{d['name']} ({d['udid']})", d['udid']) for d in entries]
                      + [('Enter and save another iPhone', 'new')])
    if selected != 'new':
        return selected

    def valid(value):
        try:
            validate_udid(value.strip())
            return True
        except ValueError as error:
            return str(error)

    udid = validate_udid(ask('text', 'iPhone UDID (idevice_id -l)', validate=valid).strip())
    name = ask('text', 'Device name', validate=lambda v: bool(v.strip()) or 'Enter a name.')
    save(name, udid)
    return udid


def check_ipa(ipa, udid):
    """Check every embedded app/extension profile; this is not Apple trust validation."""
    if not zipfile.is_zipfile(ipa):
        raise ValueError('IPA is not a valid ZIP archive.')
    with zipfile.ZipFile(ipa) as archive:
        roots = [name[:-len('Info.plist')] for name in archive.namelist()
                 if name.endswith(('.app/Info.plist', '.appex/Info.plist'))]
        if not roots:
            raise ValueError('No app bundles found in IPA.')
        for root in roots:
            try:
                profile_bytes = archive.read(root + 'embedded.mobileprovision')
            except KeyError:
                raise ValueError(f'Missing device provisioning profile: {root}') from None
            result = subprocess.run(['openssl', 'cms', '-verify', '-inform', 'DER', '-noverify'],
                                    input=profile_bytes, capture_output=True, check=True)
            profile = plistlib.loads(result.stdout)
            allowed = profile.get('ProvisionedDevices', [])
            if udid.upper() not in [value.upper() for value in allowed]:
                raise ValueError(f'This iPhone is not included in the profile for {root}. '
                                 'Create an Ad Hoc profile including this device and rebuild the IPA.')
