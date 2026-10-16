"""Terminal prompts that produce the same arguments as the explicit CLI."""

import os
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
    selected = choose('Configuration', [(str(p), str(p)) for p in paths] + [('Enter another config path', 'custom')])
    return path_prompt('Configuration file', 'file') if selected == 'custom' else selected


def arguments():
    print('ios-anywhere — local iOS builds\nUse arrow keys to choose, Enter to continue, Ctrl+C to cancel.\n')
    action = choose('What do you want to do?', [
        ('Set up build tools', 'setup'), ('Set up signing (Apple Ad Hoc profile)', 'signing-setup'),
        ('Check tools (doctor)', 'doctor'),
        ('Build an IPA', 'build'), ('Verify an IPA', 'verify'),
        ('Install an IPA on iPhone', 'install'), ('Export resources only', 'bundle'),
        ('Exit', 'exit'),
    ])
    if action == 'exit':
        return None
    if action == 'verify':
        argv = ['verify', path_prompt('IPA file', 'file')]
    elif action == 'signing-setup':
        config = select_config()
        output = path_prompt('New private signing folder', 'new', Path.home() / 'private-signing/my-app')
        argv = ['--config', config, 'signing-setup', '--output', output]
    elif action == 'install':
        config = select_config()
        ipa = path_prompt('IPA file', 'file')
        from .devices import select
        udid = select()
        argv = ['--config', config, 'install', ipa, '--udid', udid]
    else:
        engine = choose('Engine', [('Expo / React Native', 'expo'), ('Godot / GDScript', 'godot')])
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
            argv = ['--config', select_config(), '--engine', engine]
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
