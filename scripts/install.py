#!/usr/bin/env python3
"""Install the four collaborative site skills as one verified bundle."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SKILLS = ('site-builder', 'site-brief', 'site-design', 'site-check')


def copy_skill(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'),
    )


def verify_source(root: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(root / 'scripts' / 'verify_skills.py'), str(root)],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError('Source bundle failed verification:\n' + result.stdout + result.stderr)


def verify_installed(destination: Path, expected_version: str) -> None:
    for name in SKILLS:
        root = destination / name
        manifest_path = root / 'manifest.json'
        if not manifest_path.is_file():
            raise ValueError(f'Installed skill is incomplete: {name}')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('name') != name or manifest.get('version') != expected_version:
            raise ValueError(f'Installed skill metadata mismatch: {name}')
        listed = manifest.get('files')
        if not isinstance(listed, dict):
            raise ValueError(f'Installed manifest is invalid: {name}')
        import hashlib
        for relative, expected in listed.items():
            path = root / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f'Installed file failed hash verification: {name}/{relative}')


def install(root: Path, destination: Path, replace: bool) -> dict[str, object]:
    verify_source(root)
    config = json.loads((root / 'skills.json').read_text(encoding='utf-8'))
    version = config['version']

    if destination.is_symlink():
        raise ValueError('Destination skills directory must not be a symlink')
    destination.mkdir(parents=True, exist_ok=True)
    existing = [destination / name for name in SKILLS if (destination / name).exists()]
    if existing and not replace:
        names = ', '.join(path.name for path in existing)
        raise ValueError(f'Refusing partial install: already exists: {names}. Use --replace to update the whole bundle.')
    if any(path.is_symlink() for path in existing):
        raise ValueError('Refusing to replace symlinked skill directories')

    staging = Path(tempfile.mkdtemp(prefix='.site-skills-', dir=destination))
    backups = staging / '.backup'
    installed: list[Path] = []
    moved_backups: list[tuple[Path, Path]] = []
    try:
        for name in SKILLS:
            copy_skill(root / name, staging / name)
        verify_installed(staging, version)

        backups.mkdir()
        for target in existing:
            backup = backups / target.name
            os.replace(target, backup)
            moved_backups.append((backup, target))
        for name in SKILLS:
            target = destination / name
            os.replace(staging / name, target)
            installed.append(target)
        shutil.rmtree(backups, ignore_errors=True)
    except Exception:
        for target in reversed(installed):
            shutil.rmtree(target, ignore_errors=True)
        for backup, target in reversed(moved_backups):
            if backup.exists():
                os.replace(backup, target)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return {
        'bundle': config.get('bundle'),
        'version': version,
        'destination': str(destination.resolve()),
        'skills': list(SKILLS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path, help='Agent skills directory that will contain all four skill folders')
    parser.add_argument('--replace', action='store_true', help='Replace all installed bundle skills together after making verified staged copies')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        output = install(root, args.destination.expanduser().absolute(), args.replace)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
