#!/usr/bin/env python3
"""Verify the packaging and collaboration graph of the site skill suite.

This checker uses only the Python standard library.  Each skill manifest must
list every distributable file below that skill directory except
``manifest.json``. Python runtime caches are not distributable assets and are
ignored; every other unlisted file is an error.

An optional root-level ``skills.json`` may declare collaboration dependencies.
The preferred shape is::

    {
      "skills": {
        "site-builder": {"dependencies": ["site-brief"]},
        "site-brief": {"dependencies": []}
      }
    }

For compatibility, ``skills`` may also be a list of objects with ``name`` and
``dependencies``, or a top-level ``dependencies`` object may map skill names
to dependency lists.  Dependency declarations are validated against the four
skills below and checked for cycles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

EXPECTED_SKILLS = (
    "site-builder",
    "site-brief",
    "site-design",
    "site-check",
)

# Explicit manifest exception.  Everything else below a skill must be listed.
ALLOWED_UNLISTED_FILES = frozenset({"manifest.json"})

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
INLINE_LINK_RE = re.compile(
    r"!?\[[^\]]*\]\(\s*(?:<(?P<angle>[^>]+)>|(?P<plain>[^\s)]+))"
)
REFERENCE_LINK_RE = re.compile(
    r"^\s{0,3}\[[^\]]+\]:\s*(?:<(?P<angle>[^>]+)>|(?P<plain>\S+))",
    re.MULTILINE,
)
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


class Verification:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.errors: list[str] = []
        self.frontmatter_names: dict[str, str] = {}
        self.manifest_versions: dict[str, str] = {}

    def error(self, location: Path | str, message: str) -> None:
        if isinstance(location, Path):
            try:
                shown = location.resolve().relative_to(self.root).as_posix()
            except (OSError, ValueError):
                shown = str(location)
        else:
            shown = location
        self.errors.append(f"{shown}: {message}")

    def run(self, config_name: str) -> int:
        self.check_forbidden_names()
        for skill_name in EXPECTED_SKILLS:
            self.check_skill(skill_name)
        dependencies = self.load_dependencies(self.root / config_name)
        self.check_dependencies(dependencies)

        if self.errors:
            print(f"FAILED: {len(self.errors)} problem(s) found")
            for item in sorted(self.errors):
                print(f"- {item}")
            return 1

        print(f"OK: verified {len(EXPECTED_SKILLS)} skills")
        return 0

    def check_forbidden_names(self) -> None:
        """Reject packaging debris across the repository, excluding VCS internals."""
        pending = [self.root]
        while pending:
            directory = pending.pop()
            try:
                children = list(directory.iterdir())
            except OSError as exc:
                self.error(directory, f"cannot scan directory: {exc}")
                continue
            for path in children:
                if path.name == ".git" and path.parent == self.root:
                    continue
                if path.name == ".DS_Store":
                    self.error(path, "remove residual .DS_Store")
                if " 2" in path.name or " 3" in path.name:
                    self.error(path, "name contains forbidden duplicate suffix ' 2' or ' 3'")
                if path.is_dir() and not path.is_symlink():
                    pending.append(path)

    def check_skill(self, skill_name: str) -> None:
        skill_dir = self.root / skill_name
        if not skill_dir.is_dir():
            self.error(skill_dir, "expected skill directory is missing")
            return

        skill_md = skill_dir / "SKILL.md"
        fields = self.read_frontmatter(skill_md)
        if fields is not None:
            declared_name = fields.get("name", "").strip()
            description = fields.get("description", "").strip()
            if not declared_name:
                self.error(skill_md, "frontmatter field 'name' is missing or empty")
            elif declared_name != skill_name:
                self.error(
                    skill_md,
                    f"frontmatter name {declared_name!r} does not match directory {skill_name!r}",
                )
            else:
                self.frontmatter_names[skill_name] = declared_name
            if not description:
                self.error(skill_md, "frontmatter field 'description' is missing or empty")

        agent_yaml = skill_dir / "agents" / "openai.yaml"
        if not agent_yaml.is_file():
            self.error(agent_yaml, "required agent metadata is missing")

        self.check_markdown_links(skill_dir)
        self.check_manifest(skill_dir, skill_name)

    def read_frontmatter(self, path: Path) -> dict[str, str] | None:
        if not path.is_file():
            self.error(path, "SKILL.md is missing")
            return None
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            self.error(path, f"cannot read UTF-8 Markdown: {exc}")
            return None

        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            self.error(path, "YAML frontmatter must begin on the first line")
            return None
        try:
            end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        except StopIteration:
            self.error(path, "YAML frontmatter has no closing '---'")
            return None

        fields: dict[str, str] = {}
        i = 1
        while i < end:
            line = lines[i]
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$", line)
            if not match:
                i += 1
                continue
            key, raw_value = match.group(1), (match.group(2) or "").strip()
            if raw_value in {"|", ">", "|-", ">-", "|+", ">+"}:
                block: list[str] = []
                i += 1
                while i < end and (not lines[i].strip() or lines[i][:1].isspace()):
                    block.append(lines[i].strip())
                    i += 1
                fields[key] = " ".join(part for part in block if part)
                continue
            if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in "\"'":
                raw_value = raw_value[1:-1]
            fields[key] = raw_value
            i += 1
        return fields

    def check_markdown_links(self, skill_dir: Path) -> None:
        for markdown in sorted(skill_dir.rglob("*.md")):
            try:
                text = markdown.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError) as exc:
                self.error(markdown, f"cannot read UTF-8 Markdown: {exc}")
                continue
            visible_text = self.remove_fenced_code(text)
            targets: list[str] = []
            for regex in (INLINE_LINK_RE, REFERENCE_LINK_RE):
                for match in regex.finditer(visible_text):
                    targets.append(match.group("angle") or match.group("plain"))
            for target in targets:
                self.check_relative_link(markdown, target)

    @staticmethod
    def remove_fenced_code(text: str) -> str:
        output: list[str] = []
        closing_marker: str | None = None
        for line in text.splitlines():
            match = FENCE_RE.match(line)
            if match:
                marker = match.group(1)
                marker_char = marker[0]
                if closing_marker is None:
                    closing_marker = marker_char
                    output.append("")
                    continue
                if marker_char == closing_marker:
                    closing_marker = None
                    output.append("")
                    continue
            output.append("" if closing_marker else line)
        return "\n".join(output)

    def check_relative_link(self, source: Path, raw_target: str) -> None:
        target = raw_target.strip()
        if (
            not target
            or target.startswith("#")
            or target.startswith("/")
            or target.startswith("//")
            or SCHEME_RE.match(target)
        ):
            return

        split = urlsplit(target)
        path_text = unquote(split.path)
        if not path_text:
            return
        destination = (source.parent / path_text).resolve()
        try:
            destination.relative_to(self.root)
        except ValueError:
            self.error(source, f"relative link escapes repository: {raw_target!r}")
            return
        if not destination.exists():
            self.error(source, f"broken relative link: {raw_target!r}")

    def check_manifest(self, skill_dir: Path, skill_name: str) -> None:
        manifest_path = skill_dir / "manifest.json"
        if not manifest_path.is_file():
            self.error(manifest_path, "manifest is missing")
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self.error(manifest_path, f"cannot parse JSON: {exc}")
            return
        if not isinstance(manifest, dict):
            self.error(manifest_path, "manifest root must be an object")
            return
        if manifest.get("name") != skill_name:
            self.error(manifest_path, f"manifest name must be {skill_name!r}")
        version = manifest.get("version")
        if not isinstance(version, str) or not version:
            self.error(manifest_path, "manifest version must be a non-empty string")
        else:
            self.manifest_versions[skill_name] = version
        files = manifest.get("files")
        if not isinstance(files, dict):
            self.error(manifest_path, "'files' must be an object of path -> sha256")
            return

        listed: set[str] = set()
        for raw_path, digest in files.items():
            if not isinstance(raw_path, str):
                self.error(manifest_path, "every manifest file path must be a string")
                continue
            normalized = self.normalize_manifest_path(raw_path)
            if normalized is None:
                self.error(manifest_path, f"unsafe or non-canonical file path: {raw_path!r}")
                continue
            if normalized in listed:
                self.error(manifest_path, f"duplicate normalized file path: {normalized!r}")
                continue
            listed.add(normalized)

            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                self.error(manifest_path, f"invalid sha256 for {normalized!r}")
                continue
            file_path = skill_dir / Path(*PurePosixPath(normalized).parts)
            if not file_path.is_file():
                self.error(manifest_path, f"listed file is missing: {normalized!r}")
                continue
            try:
                actual_digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            except OSError as exc:
                self.error(file_path, f"cannot hash file: {exc}")
                continue
            if actual_digest != digest:
                self.error(
                    manifest_path,
                    f"sha256 mismatch for {normalized!r}: expected {digest}, got {actual_digest}",
                )

        actual = {
            path.relative_to(skill_dir).as_posix()
            for path in skill_dir.rglob("*")
            if path.is_file() and not self.is_runtime_cache(path.relative_to(skill_dir))
        }
        for path in sorted(actual - listed - ALLOWED_UNLISTED_FILES):
            self.error(skill_dir / Path(*PurePosixPath(path).parts), "file is not listed in manifest")
        for path in sorted(listed - actual):
            self.error(manifest_path, f"manifest lists absent file: {path!r}")

    @staticmethod
    def is_runtime_cache(path: Path) -> bool:
        return "__pycache__" in path.parts or path.suffix == ".pyc"

    @staticmethod
    def normalize_manifest_path(raw_path: str) -> str | None:
        if "\\" in raw_path or not raw_path or raw_path.startswith("/"):
            return None
        path = PurePosixPath(raw_path)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            return None
        normalized = path.as_posix()
        return normalized if normalized == raw_path else None

    def load_dependencies(self, config_path: Path) -> dict[str, set[str]]:
        graph = {name: set() for name in EXPECTED_SKILLS}
        if not config_path.exists():
            self.error(config_path, "required bundle dependency config is missing")
            return graph
        if not config_path.is_file():
            self.error(config_path, "dependency config is not a regular file")
            return graph
        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self.error(config_path, f"cannot parse dependency config: {exc}")
            return graph
        if not isinstance(config, dict):
            self.error(config_path, "dependency config root must be an object")
            return graph

        bundle_version = config.get("version")
        if not isinstance(bundle_version, str) or not bundle_version:
            self.error(config_path, "bundle version must be a non-empty string")
        else:
            for name, version in self.manifest_versions.items():
                if version != bundle_version:
                    self.error(config_path, f"{name!r} manifest version {version!r} does not match bundle {bundle_version!r}")

        declarations: list[tuple[Any, Any]] = []
        skills = config.get("skills", {})
        if isinstance(skills, dict):
            for name, spec in skills.items():
                if isinstance(spec, dict):
                    declared_version = spec.get("version")
                    actual_version = self.manifest_versions.get(name)
                    if declared_version != actual_version:
                        self.error(config_path, f"{name!r} config version {declared_version!r} does not match manifest {actual_version!r}")
                    deps = spec.get("dependencies", spec.get("depends_on", []))
                elif isinstance(spec, list):
                    deps = spec
                else:
                    self.error(config_path, f"skill {name!r} must map to an object or list")
                    continue
                declarations.append((name, deps))
        elif isinstance(skills, list):
            for spec in skills:
                if isinstance(spec, str):
                    declarations.append((spec, []))
                elif isinstance(spec, dict):
                    declarations.append(
                        (spec.get("name"), spec.get("dependencies", spec.get("depends_on", [])))
                    )
                else:
                    self.error(config_path, "each item in 'skills' must be a name or object")
        else:
            self.error(config_path, "'skills' must be an object or list")

        dependency_map = config.get("dependencies", {})
        if not isinstance(dependency_map, dict):
            self.error(config_path, "top-level 'dependencies' must be an object")
        else:
            declarations.extend(dependency_map.items())

        declared_sources: set[str] = set()
        for source, dependencies in declarations:
            if not isinstance(source, str) or source not in graph:
                self.error(config_path, f"dependency source is not a known skill: {source!r}")
                continue
            if not isinstance(dependencies, list) or any(
                not isinstance(item, str) or not item for item in dependencies
            ):
                self.error(config_path, f"dependencies for {source!r} must be non-empty strings")
                continue
            declared_sources.add(source)
            graph[source].update(dependencies)
        for missing in sorted(set(EXPECTED_SKILLS) - declared_sources):
            self.error(config_path, f"bundle does not declare required skill {missing!r}")
        return graph

    def check_dependencies(self, graph: dict[str, set[str]]) -> None:
        available = set(self.frontmatter_names.values())
        for source, dependencies in graph.items():
            for dependency in dependencies:
                if dependency not in EXPECTED_SKILLS:
                    self.error("skills.json", f"{source!r} declares unknown dependency {dependency!r}")
                elif dependency not in available:
                    self.error("skills.json", f"{source!r} dependency {dependency!r} does not exist")

        state: dict[str, int] = {name: 0 for name in graph}
        stack: list[str] = []
        reported: set[tuple[str, ...]] = set()

        def visit(node: str) -> None:
            state[node] = 1
            stack.append(node)
            for dependency in sorted(graph[node]):
                if dependency not in graph:
                    continue
                if state[dependency] == 0:
                    visit(dependency)
                elif state[dependency] == 1:
                    start = stack.index(dependency)
                    cycle = tuple(stack[start:] + [dependency])
                    if cycle not in reported:
                        reported.add(cycle)
                        self.error("skills.json", "circular dependency: " + " -> ".join(cycle))
            stack.pop()
            state[node] = 2

        for skill_name in EXPECTED_SKILLS:
            if state[skill_name] == 0:
                visit(skill_name)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: parent of this script directory)",
    )
    parser.add_argument(
        "--config",
        default="skills.json",
        help="root-relative dependency config name (default: skills.json)",
    )
    args = parser.parse_args(argv)
    config = Path(args.config)
    if config.is_absolute() or ".." in config.parts:
        parser.error("--config must be a safe path relative to the repository root")
    return args


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.root.is_dir():
        print(f"ERROR: repository root is not a directory: {args.root}", file=sys.stderr)
        return 2
    return Verification(args.root).run(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
