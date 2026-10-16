"""Terminal prompts that produce the same arguments as the explicit CLI."""

import os
import json
from pathlib import Path
import shlex

from .config import default_config


def ask(kind, message, **kwargs):
    import questionary
    answer = getattr(questionary, kind)(message, **kwargs).ask()
    if answer is None:
        raise KeyboardInterrupt
    return answer


def choose(message, choices):
    return ask('select', message, choices=[{'name': label, 'value': value} for label, value in choices])


def validate_path(value, kind):
    if not value.strip():
        return 'Enter a path.'
    path = Path(value).expanduser()
    if kind == 'file' and not path.is_file():
        return 'Choose an existing file.'
    if kind == 'directory' and not path.is_dir():
        return 'Choose an existing folder.'
    if kind == 'new' and (path.exists() or path.is_symlink()):
        return 'Choose a new path; existing files and folders are preserved.'
    return True


def path_prompt(message, kind, default=''):
    value = ask('path', message, default=str(default), only_directories=kind == 'directory',
                validate=lambda value: validate_path(value, kind))
    return str(Path(value).expanduser().absolute())


def configurations():
    root = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config').expanduser()
    found = {p.absolute() for name in ('ios-anywhere', 'ios-linux') for p in (root / name).glob('*.json') if p.is_file()}
    preferred = default_config().absolute()
    return sorted(found, key=lambda p: (p != preferred, str(p)))


def select_config():
    paths = configurations()
    if not paths:
        print('No saved configurations found. Run setup first, or select a config stored elsewhere.')
    print('A configuration points to installed build tools. It does not contain your Apple signing credentials.')
    selected = choose('Which installed tools should we use?', [(config_label(p), str(p)) for p in paths] + [('Enter another config path', 'custom')])
    return path_prompt('Configuration file', 'file') if selected == 'custom' else selected


def config_label(path):
    try:
        tools = json.loads(path.read_text()).get('toolchain', 'not configured')
    except (OSError, ValueError, AttributeError):
        return f'{path.name} — unreadable configuration ({path})'
    name = {'expo': 'Expo / React Native', 'godot': 'Godot'}.get(path.stem, path.stem)
    return f'{name} — tools: {tools} ({path})'


def signing_folder(default=None):
    print('Save the Apple certificate, provisioning profile and credentials.json in a NEW private folder.\n'
          'This is an output folder, not your project. Keep it outside Git and do not share it.')
    return path_prompt('Where should we save your signing files?', 'new',
                       default or Path.home() / 'private-signing/my-app')


def menu():
    while True:
        action = choose('What do you want to do?', [
            ('Get started — guided setup, build and install', 'guided'),
            ('Build an IPA', 'build'), ('Install on iPhone', 'install'),
            ('Manage signing & devices', 'manage'), ('Advanced', 'advanced'), ('Exit', 'exit')])
        if action in ('manage', 'advanced'):
            choices = ([('Create Apple signing credentials', 'signing-setup'),
                        ('Choose or save an iPhone', 'device')] if action == 'manage' else
                       [('Set up build tools', 'setup'), ('Check tools (doctor)', 'doctor'),
                        ('Verify an IPA', 'verify'), ('Export resources only', 'bundle')])
            action = choose('Choose an action', choices + [('Back', 'back')])
            if action == 'back':
                continue
        return action


def arguments(action=None, engine=None, config=None):

    print('ios-anywhere — local iOS builds\nUse arrow keys to choose, Enter to continue, Ctrl+C to cancel.\n')
    action = action or menu()
    while action == 'guided':
        from .wizard import run
        run()
        action = menu()
    if action == 'device':
        from .devices import select
        select()
        return None
    if action == 'exit':
        return None
    if action == 'verify':
        argv = ['verify', path_prompt('IPA file', 'file')]
    elif action == 'signing-setup':
        config = config or select_config()
        output = signing_folder()
        argv = ['--config', config, 'signing-setup', '--output', output]
    elif action == 'install':
        config = config or select_config()
        ipa = path_prompt('IPA file', 'file')
        from .devices import select
        udid = select()
        argv = ['--config', config, 'install', ipa, '--udid', udid]
    else:
        engine = engine or choose('Engine', [('Expo / React Native', 'expo'), ('Godot / GDScript', 'godot')])
        if action == 'setup':
            root = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config').expanduser()
            print('Setup creates a new installation. Existing configs and toolchains are preserved.')
            config = path_prompt('New configuration file', 'new', root / 'ios-anywhere' / f'{engine}.json')
            tools = path_prompt('New toolchain folder', 'new', Path.home() / '.local/share/ios-anywhere' / f'{engine}-toolchain')
            source = choose('Apple SDK source', [('Import local SDKs', 'local'), ('Download from unofficial mirror', 'mirror')])
            argv = ['--config', config, 'setup', '--engine', engine, '--toolchain', tools, '--sdk-source', source]
            if source == 'local':
                label = 'Folder containing iPhoneOS26.4.sdk and iPhoneOS26.5.sdk' if engine == 'expo' else 'iPhoneOS18.5.sdk folder'
                argv += ['--sdk', path_prompt(label, 'directory')]
        else:
            argv = ['--config', config or select_config(), '--engine', engine]
            if action == 'doctor':
                argv += ['doctor']
            else:
                project = path_prompt('Project folder', 'directory')
                argv += ['--project', project]
                if engine == 'godot':
                    bundle = ask('text', 'Bundle ID (must match the provisioning profile)',
                                 validate=lambda v: bool(v.strip()) or 'Enter a bundle ID.').strip()
                    argv += ['--bundle-id', bundle]
                if action == 'build':
                    argv += ['--credentials', path_prompt('Signing credentials JSON', 'file')]
                    output = path_prompt('New output IPA', 'new', Path(project) / 'iosapp.ipa')
                    argv += ['build', '--output', output]
                else:
                    argv += ['bundle']
    print('\nCommand: ' + shlex.join(['ios-anywhere', *argv]) + '\n')
    return argv
