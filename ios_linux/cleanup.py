"""Remove regenerable build files only, keeping sources and diagnostic logs."""

import fcntl
import os
from pathlib import Path
import shutil


EXPO = ('build', 'project/node_modules', 'project/ios/Pods')
GODOT = ('project/.godot', 'stage', 'Game.pck', 'Game', 'dummy.o', 'os_version_check.o')


def safe_path(path, root):
    # Never follow a link out of the configured cache, including parent links.
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return False
    return True


def candidates(config):
    root = config.cache.resolve()
    tools = config.toolchain.resolve()
    if root == Path('/') or root == Path.home().resolve() or root == tools or tools.is_relative_to(root) or root.is_relative_to(tools):
        raise ValueError('Unsafe cache location; refusing cleanup.')
    found = []
    for engine, names, marker in [('expo', EXPO, 'package.json'), ('godot', GODOT, 'project.godot')]:
        folder = root / engine
        if not folder.is_dir() or folder.is_symlink():
            continue
        for job in sorted(folder.iterdir()):
            if not job.is_dir() or not safe_path(job / 'project' / marker, root) or not (job / 'project' / marker).is_file():
                continue
            for name in names:
                path = job / name
                if path.exists() and safe_path(path, root):
                    found.append(path)
    return found


def size(path):
    if path.is_file():
        return path.stat().st_size
    total = 0
    for folder, _, files in os.walk(path, followlinks=False):
        for name in files:
            file = Path(folder) / name
            if not file.is_symlink():
                total += file.stat().st_size
    return total


def clean(config):
    from .interactive import ask
    paths = candidates(config)
    if not paths:
        print('No regenerable build caches found.')
        return
    # Keep the same lock inode as builds; never delete build.lock or the cache root.
    with (config.cache / 'build.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('A build is running. Wait for it to finish before cleaning caches.') from None
        paths = candidates(config)
        total = sum(size(p) for p in paths)
        for path in paths:
            print(f'  {path}')
        print(f'Approximate cache size: {total / 1024**3:.2f} GiB.\n'
              'Keeps toolchains, signing files, source snapshots, logs and exported IPAs.\n'
              'The next build will regenerate these files and may download dependencies again.')
        if not ask('confirm', 'Delete these build caches?', default=False):
            print('Cleanup cancelled.')
            return
        for path in paths:
            if not safe_path(path, config.cache.resolve()):
                raise ValueError('Cache path changed; cleanup stopped.')
            if path.is_dir():
                # CocoaPods caches can contain read-only directories.
                for folder, _, _ in os.walk(path, followlinks=False):
                    directory = Path(folder)
                    directory.chmod(directory.stat().st_mode | 0o700)
                shutil.rmtree(path)
            else:
                path.unlink()
        print(f'Build caches removed ({total / 1024**3:.2f} GiB of file contents).')
