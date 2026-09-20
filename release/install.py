#!/usr/bin/env python3
"""Install a self-contained sibling bundle; roll back recoverable failures.

Stop agents using this installation before replacement. Per-directory moves
are not an atomic four-directory swap. A process kill/power loss leaves the
lock and staging directory for manual recovery; it is never silently retried.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

INSTRUCTION_REL = Path("site-builder/references/AGENTS.md")
LOCK_NAME = ".site-skills-install.lock"
NAME_RE = re.compile(r"[a-z][a-z0-9-]*\Z")


def load_bundle(root: Path) -> dict:
    root = root.resolve()
    config = json.loads((root / "skills.json").read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("skills.json must be a JSON object")
    skills = config.get("skills")
    version = config.get("version")
    if version not in (1, "1.0.0", "1.1", 3) or not isinstance(skills, dict) or not skills:
        raise ValueError("invalid skills.json")
    if not isinstance(config.get("bundle"), str) or not config["bundle"].strip():
        raise ValueError("bundle name is required")
    if "site-builder" not in skills:
        raise ValueError("bundle must include site-builder")
    if not (root / "AGENTS.md").is_file():
        raise ValueError("missing bundle instruction file: AGENTS.md")
    if (root / "AGENTS.md").is_symlink():
        raise ValueError("bundle instruction file must not be a symlink")
    for name, details in skills.items():
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise ValueError(f"unsafe skill name: {name!r}")
        if not isinstance(details, dict) or not isinstance(details.get("directory"), str):
            raise ValueError(f"invalid skill declaration: {name}")
        rel = Path(details["directory"])
        if not rel.parts or rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"unsafe skill directory: {name}")
        source = root / rel
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError(f"skill source escapes bundle: {name}")
        skill_file = source / "SKILL.md"
        if not skill_file.is_file():
            raise ValueError(f"missing skill source: {source}")
        # Following archive symlinks can copy files outside the release or loop.
        if any(path.is_symlink() for path in source.rglob("*")):
            raise ValueError(f"symlinks are not supported in skill source: {name}")
        frontmatter = skill_file.read_text(encoding="utf-8").split("---", 2)
        pattern = r"(?m)^name:\s*" + re.escape(name) + r"\s*$"
        if len(frontmatter) < 3 or not re.search(pattern, frontmatter[1]):
            raise ValueError(f"skill name mismatch: {name}")
    return config


def install(root: Path, destination: Path, replace: bool = False) -> dict:
    root = root.resolve()
    destination = destination.expanduser().resolve()
    config = load_bundle(root)
    skills = config["skills"]
    targets = {name: destination / name for name in skills}
    sources = [(root / details["directory"]).resolve() for details in skills.values()]
    if destination == root or any(destination.is_relative_to(source) for source in sources):
        raise ValueError("destination must not overlap the source bundle")
    for target in targets.values():
        if target.is_symlink():
            raise ValueError(f"refusing to replace a symlink: {target}")
        if target.exists() and not target.is_dir():
            raise ValueError(f"skill target is not a directory: {target}")
        if any(source.is_relative_to(target) or target.is_relative_to(source) for source in sources):
            raise ValueError("destination must not overlap the source bundle")
    existing = [name for name, target in targets.items() if target.exists()]
    if existing and not replace:
        raise ValueError("already installed: " + ", ".join(sorted(existing)))
    destination.mkdir(parents=True, exist_ok=True)
    lock = destination / LOCK_NAME
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError(
            f"installation is locked: {lock}; check for a running installer or recover an interrupted install"
        ) from exc
    staging = None
    retain_recovery = False
    installed = []
    backed_up = []
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"pid": os.getpid(), "destination": str(destination)}))
        staging = Path(tempfile.mkdtemp(prefix="site-skills-", dir=destination))
        new = staging / "new"
        backup = staging / "backup"
        new.mkdir()
        backup.mkdir()
        for name, details in skills.items():
            shutil.copytree(
                root / details["directory"], new / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )
        instructions = new / INSTRUCTION_REL
        instructions.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / "AGENTS.md", instructions)
        # Never modify the host's own AGENTS.md. This path remains available
        # after the downloaded source release is removed.
        (staging / "recovery.json").write_text(json.dumps({
            "destination": str(destination), "skills": list(skills),
            "old_locations": {name: str(backup / name) for name in existing},
        }, indent=2), encoding="utf-8")
        try:
            for name, target in targets.items():
                if target.exists():
                    os.replace(target, backup / name)
                    backed_up.append(name)
                os.replace(new / name, target)
                installed.append(name)
        except OSError as original_error:
            recovery_errors = []
            for name in reversed(installed):
                try:
                    shutil.rmtree(targets[name])
                except OSError as exc:
                    recovery_errors.append(str(exc))
            for name in reversed(backed_up):
                try:
                    os.replace(backup / name, targets[name])
                except OSError as exc:
                    recovery_errors.append(str(exc))
            if recovery_errors:
                retain_recovery = True
                raise RuntimeError(
                    f"installation failed ({original_error}); rollback incomplete; "
                    f"recover using {staging / 'recovery.json'}; lock retained: {lock}; "
                    + "; ".join(recovery_errors)
                ) from original_error
            raise
    finally:
        if not retain_recovery:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            lock.unlink(missing_ok=True)

    return {
        "bundle": config["bundle"], "destination": str(destination),
        "skills": sorted(skills),
        "instruction_file": str(destination / INSTRUCTION_REL),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    try:
        result = install(Path(__file__).resolve().parent, args.destination, args.replace)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
