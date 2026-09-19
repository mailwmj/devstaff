#!/usr/bin/env python3
"""Install the four skills as a sibling bundle."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path


def load_bundle(root: Path) -> dict:
    config = json.loads((root / "skills.json").read_text(encoding="utf-8"))
    skills = config.get("skills")
    version = config.get("version")
    if version not in {1, "1.0.0", "1.1", 3} or not isinstance(skills, dict) or not skills:
        raise ValueError("invalid skills.json")
    for name, details in skills.items():
        if not isinstance(details, dict) or not isinstance(details.get("directory"), str):
            raise ValueError(f"invalid skill declaration: {name}")
        source = root / details["directory"]
        skill_file = source / "SKILL.md"
        if not skill_file.is_file():
            raise ValueError(f"missing skill source: {source}")
        frontmatter = skill_file.read_text(encoding="utf-8").split("---", 2)
        if len(frontmatter) < 3 or f"name: {name}" not in frontmatter[1]:
            raise ValueError(f"skill name mismatch: {name}")
    return config


def install(root: Path, destination: Path, replace: bool = False) -> dict:
    config = load_bundle(root)
    destination.mkdir(parents=True, exist_ok=True)
    skills = config["skills"]
    targets = {name: destination / name for name in skills}
    existing = [name for name, target in targets.items() if target.exists()]
    if existing and not replace:
        raise ValueError("already installed: " + ", ".join(sorted(existing)))

    staging = Path(tempfile.mkdtemp(prefix="site-skills-", dir=destination))
    try:
        for name, details in skills.items():
            shutil.copytree(
                root / details["directory"],
                staging / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )
        for name, target in targets.items():
            if target.exists():
                shutil.rmtree(target)
            os.replace(staging / name, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return {
        "bundle": config["bundle"],
        "destination": str(destination.resolve()),
        "skills": sorted(skills),
        "instruction_file": str((root / "AGENTS.md").resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    try:
        result = install(root, args.destination.expanduser().resolve(), args.replace)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
