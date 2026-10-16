"""Guided workflow using the same validated commands as the CLI."""

from pathlib import Path
import shlex
import subprocess

from . import interactive as ui


def execute(argv):
    from .cli import execute as command
    while True:
        print('\nCommand: ' + shlex.join(['ios-anywhere', *argv]))
        try:
            command(argv)
            return True
        except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
            print(f'Error: {error}')
            if not ui.ask('confirm', 'Retry this step with the same choices?', default=False):
                return False


def run():
    print('We will check tools, choose signing credentials, build, then optionally install.\n'
          'Existing credentials can be reused. Ctrl+C exits without undoing completed steps.')
    engine = ui.choose('What kind of project?', [('Expo / React Native', 'expo'), ('Godot', 'godot')])
    while True:
        source = ui.choose('Build tools', [('Use an existing installation', 'existing'),
                                          ('Set up tools on this computer', 'new'), ('Back to main menu', 'back')])
        if source == 'back':
            return
        if source == 'new':
            argv = ui.arguments('setup', engine=engine)
            if not execute(argv):
                continue
            config = argv[argv.index('--config') + 1]
            if not Path(config).is_file():
                print('Setup was cancelled; no configuration was created.')
                continue
        else:
            config = ui.select_config()
        if execute(['--config', config, '--engine', engine, 'doctor']):
            break
    project = ui.path_prompt('Project folder', 'directory')
    while True:
        source = ui.choose('Apple signing credentials', [('Use an existing credentials.json', 'existing'),
                                                       ('Create credentials with my Apple account', 'new')])
        if source == 'existing':
            credentials = ui.path_prompt('Existing credentials.json', 'file')
            break
        output = ui.signing_folder(Path.home() / 'private-signing' / Path(project).name)
        # Account mutations must never be automatically retried after a partial failure.
        from .cli import execute as command
        try:
            command(['--config', config, 'signing-setup', '--output', output])
        except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
            print(f'Signing failed: {error}\nCheck the private output folder before creating another profile.')
            continue
        credentials = str(Path(output) / 'credentials.json')
        if Path(credentials).is_file():
            break
        print('Signing setup was cancelled. Choose existing credentials or start again.')
    bundle = None
    if engine == 'godot':
        bundle = ui.ask('text', 'Bundle ID (must match your provisioning profile)',
                        validate=lambda v: bool(v.strip()) or 'Enter a bundle ID.').strip()
    output = ui.path_prompt('New output IPA', 'new', Path(project) / 'iosapp.ipa')
    while True:
        identity_error = None
        if engine == 'expo':
            from . import expo, signing
            from .config import Config
            try:
                bundle = expo.bundle_identifier(Config.load(Path(config)), Path(project))
                signing.check_identity(Path(credentials), bundle)
            except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
                identity_error = str(error)
                print(f'Identity check: {error}')
        print(f'Bundle ID: {bundle or "not configured"}')
        print(f'\nEngine: {engine}\nTools config: {config}\nProject: {project}\n'
              f'Credentials: {credentials}\nOutput: {output}')
        choice = ui.choose('Ready to build?', [('Build', 'build'), ('Change project', 'project'),
                          ('Change credentials', 'credentials'), ('Change output', 'output')] + ([('Change bundle ID', 'bundle')] if engine == 'godot' else []) + [('Cancel', 'cancel')])
        if choice == 'cancel':
            return
        if choice == 'project':
            project = ui.path_prompt('Project folder', 'directory', project)
            output = ui.path_prompt('New output IPA', 'new', Path(project) / 'iosapp.ipa')
        elif choice == 'credentials':
            credentials = ui.path_prompt('Existing credentials.json', 'file', credentials)
        elif choice == 'bundle':
            bundle = ui.ask('text', 'Bundle ID (must match your provisioning profile)', default=bundle,
                            validate=lambda v: bool(v.strip()) or 'Enter a bundle ID.').strip()
        elif choice == 'output':
            output = ui.path_prompt('New output IPA', 'new', output)
        else:
            if identity_error:
                print('Fix the project configuration or choose matching credentials before building.')
                continue
            argv = ['--config', config, '--engine', engine, '--project', project, '--credentials', credentials]
            if engine == 'godot' and bundle:
                argv += ['--bundle-id', bundle]
            if execute(argv + ['build', '--output', output]):
                break
    if ui.ask('confirm', 'Install this IPA on an iPhone now?', default=False):
        from .devices import select
        execute(['--config', config, 'install', output, '--udid', select()])
