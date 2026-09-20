#!/usr/bin/env python3
"""Build the platform package under ``dist/`` from ``release/package-files.txt``.

The manifest is the single source of truth for what ships: every listed file is
copied into ``dist/<id>-<version>/`` and packed into a deterministic zip. The
zip is byte-stable for the same manifest -- sorted entries, fixed 1980
timestamps and fixed unix permissions -- so rebuilding after a no-op change
does not produce a new artifact.

Run this after changing anything under ``release/``. ``tests/test_bundle.py``
verifies the built package against the manifest when ``dist/`` exists, so a
stale package fails the dev test suite instead of shipping.

Python 3.9+, standard library only.
"""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
DIST = ROOT / "dist"
MANIFEST = RELEASE / "package-files.txt"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FILE_MODE = 0o100644


def listed_paths() -> list[str]:
    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def package_name() -> str:
    metadata = json.loads((RELEASE / "metadata.json").read_text(encoding="utf-8"))
    return f"{metadata['id']}-{metadata['version']}"


def clean_stale(name: str) -> None:
    """Remove earlier builds of the same package, keep unrelated files."""
    if not DIST.is_dir():
        return
    keep = {name, f"{name}.zip"}
    for path in DIST.glob("*"):
        if path.name in keep:
            continue
        if path.name.startswith(name.rsplit("-", 1)[0] + "-"):
            shutil.rmtree(path) if path.is_dir() else path.unlink()


def build() -> Path:
    paths = listed_paths()
    missing = [rel for rel in paths if not (RELEASE / rel).is_file()]
    if missing:
        raise SystemExit("package-files.txt lists missing files: " + ", ".join(missing))

    name = package_name()
    target = DIST / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for rel in paths:
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RELEASE / rel, destination)

    archive = DIST / f"{name}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in sorted(paths):
            info = zipfile.ZipInfo(rel, date_time=ZIP_TIMESTAMP)
            info.create_system = 3  # unix, so the permission bits below apply
            info.external_attr = FILE_MODE << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, (RELEASE / rel).read_bytes())

    clean_stale(name)
    return archive


def main() -> int:
    archive = build()
    print(f"built {archive.relative_to(ROOT)} with {len(listed_paths())} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
