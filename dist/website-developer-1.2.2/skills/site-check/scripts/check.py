#!/usr/bin/env python3
"""Lightweight, deterministic check protocol for site-check.

Generates a verification plan and validates check reports against the check protocol.
It never starts a browser: it only reads the contract and source,
computes SHA-256 fingerprints, and checks that a report conforms to the
gating, dependency, hash-invalidation and mode rules. Python 3.9+, stdlib only.

The protocol is organized in six levels (L0-L5) over eight axes:

    L0  contract          static, no browser
    L1  static_build      static, no browser
    L2  core_task         browser
    L3  negative_path     browser
    L4  visual_desktop / visual_mobile   browser, per viewport
    L5  reopen / risk     browser

Rules encoded here:
  * L0/L1 failure does not start the browser -- ``blocked`` or ``not_run``
    both count as failed; browser axes must be ``not_run``.
  * A visual failure only re-verifies the affected page/state/viewport (VA),
    not every viewport; failed VAs are carried in the report.
  * A contract SHA-256 change invalidates every axis; a source SHA-256 change
    invalidates L1-L5 (the contract lives under ``.site`` and is hashed
    separately, so L0 stays valid when only source changes). Fingerprints are
    an identity check: a report whose fingerprints do not match the current
    tree is not valid, and a fresh report is written for the current tree
    rather than an old one being re-scoped.
  * An axis that claims ``verified`` must record what it examined.
  * guided may honestly report ``limited``; strict cannot be ``limited`` and a
    strict ``verified`` requires independent verification.
  * When an axis dependency is ambiguous, the scope escalates to guided-core
    (contract + static_build + core_task) rather than silently shrinking.
  * --changed-from REF accepts two kinds of input with no ambiguity: a path to
    a prior check report/plan JSON or a git commit reference (e.g. HEAD~1). It
    reports the files that changed; deciding what to re-verify stays with the
    agent, because a file→axis mapping cannot be trusted (a CSS rule can hide
    the core task just as easily as it can move a pixel).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stdin, 'reconfigure'):
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')

CONTRACT_REL_PATH = '.site/design/surface-brief.md'
STATE_REL_PATH = '.site/state.json'
CONTRACT_BLOCK_RE = re.compile(r'```(?:site-contract|v3-contract)\n(.*?)\n```', re.DOTALL)
ID_TOKEN_RE = re.compile(r'`([A-Z]{2}-\d{2})`')

AXES = ('contract', 'static_build', 'core_task', 'negative_path',
        'visual_desktop', 'visual_mobile', 'reopen', 'risk')
STATIC_AXES = ('contract', 'static_build')
BROWSER_AXES = ('core_task', 'negative_path', 'visual_desktop',
                'visual_mobile', 'reopen', 'risk')
# Non-negotiable guided floor; "依赖不明确时升级 guided-core".
GUIDED_CORE = ('contract', 'static_build', 'core_task')
VA_AXIS_VALUES = ('core_task', 'visual_desktop', 'visual_mobile', 'reopen')
VERIFY_STATUSES = ('verified', 'limited', 'blocked', 'not_run')
DELIVERABLE_STATUSES = ('verified', 'limited', 'blocked')

LEVELS = (
    {'level': 'L0', 'axes': ['contract'], 'browser': False, 'depends_on': []},
    {'level': 'L1', 'axes': ['static_build'], 'browser': False, 'depends_on': ['L0']},
    {'level': 'L2', 'axes': ['core_task'], 'browser': True, 'depends_on': ['L1']},
    {'level': 'L3', 'axes': ['negative_path'], 'browser': True, 'depends_on': ['L2']},
    {'level': 'L4', 'axes': ['visual_desktop', 'visual_mobile'], 'browser': True, 'depends_on': ['L2']},
    {'level': 'L5', 'axes': ['reopen', 'risk'], 'browser': True, 'depends_on': ['L3', 'L4']},
)
# If an axis fails, its dependents must be re-verified.
DEPENDENTS = {
    'contract': ['static_build', 'core_task', 'negative_path', 'visual_desktop', 'visual_mobile', 'reopen', 'risk'],
    'static_build': ['core_task', 'negative_path', 'visual_desktop', 'visual_mobile', 'reopen', 'risk'],
    'core_task': ['negative_path', 'visual_desktop', 'visual_mobile', 'reopen', 'risk'],
    'negative_path': ['reopen', 'risk'],
    'visual_desktop': ['reopen', 'risk'],
    'visual_mobile': ['reopen', 'risk'],
    'reopen': [],
    'risk': [],
}
# A source SHA-256 change invalidates everything built on the source; the
# contract is a separate file under .site, so L0 stays valid when only source changes.
SOURCE_INVALIDATES = ('static_build', 'core_task', 'negative_path', 'visual_desktop', 'visual_mobile', 'reopen', 'risk')

# Tooling and VCS bookkeeping: never product source, at any depth.
SOURCE_IGNORE = {'.site', '.SITE', '.v3', '.git', 'node_modules', '__pycache__', '.DS_Store',
                 '.playwright-cli'}
# Runtime state and build output, matched only at the project root. Runtime
# files are excluded by what they are -- a state-file suffix (``.db`` and
# friends) -- never by a name product source also uses. ``uploads`` stays
# because a product whose core task writes an upload would otherwise
# invalidate its own report by doing the task; ``data`` was removed because a
# static site's ``data/products.json`` is product content, and excluding it
# made a report about the site silently independent of that content.
# Build-output directories stay: the source that produces them is what the
# report is about. ``plan`` lists what was excluded either way.
SOURCE_IGNORE_ROOT = {'uploads', 'dist', 'build', '.cache', '.next', 'coverage'}
# Files that change while the product is being used, wherever they sit.
SOURCE_IGNORE_SUFFIXES = ('.db', '.db-wal', '.db-shm', '.db-journal',
                          '.sqlite', '.sqlite3', '.log')
# Agent instruction files: how the toolchain is told to work, never product.
SOURCE_IGNORE_ROOT_FILES = {'AGENTS.md', 'CLAUDE.md'}
# The bundle ships as sibling skill directories plus its installer, and it can
# be installed inside the project root. ``skills.json`` declares which
# directories those are, so the presence of that file -- not a directory name
# -- is what marks the toolchain: a product directory that happens to reuse a
# skill's name stays in the fingerprint. Editing a planning skill is not
# editing the site, and letting it void an open verification round teaches the
# wrong lesson about when to fix a reference file.
BUNDLE_DECLARATION = 'skills.json'
BUNDLE_ROOT_FILES = {'skills.json', 'install.py'}
# plan reports the excluded paths so a wrong exclusion is visible, not silent.
SOURCE_EXCLUDED_LIMIT = 50
CHANGED_FILES_LIMIT = 50


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contract_path(root) -> Path:
    for rel in (CONTRACT_REL_PATH, '.SITE/design/surface-brief.md', '.v3/design/surface-brief.md'):
        candidate = Path(root) / rel
        if candidate.is_file():
            return candidate
    return Path(root) / CONTRACT_REL_PATH


def _parse_contract_block(text: str) -> dict:
    match = CONTRACT_BLOCK_RE.search(text)
    if not match:
        raise ValueError('contract block is missing')
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f'contract block is not valid JSON: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError('contract block must be a JSON object')
    return data


def _strip_contract_block(text: str) -> str:
    return CONTRACT_BLOCK_RE.sub('', text)


def _contract_lists(data: dict) -> dict:
    lists = {}
    for key in ('acceptance', 'intentional_exceptions'):
        value = data.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f'contract field {key} must be a list')
        lists[key] = [str(item) for item in value]
    return lists


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def _table(body: str, *header_markers: str) -> tuple[list[str], list[list[str]]]:
    """First markdown table whose header contains every marker; (header, rows)."""
    lines = body.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip().startswith('|') and index + 1 < len(lines):
            separator = lines[index + 1].strip()
            if separator.startswith('|') and set(separator) <= set('|:- '):
                header = _split_row(line)
                if all(any(marker in cell for cell in header) for marker in header_markers):
                    index += 2
                    rows = []
                    while index < len(lines) and lines[index].strip().startswith('|'):
                        rows.append(_split_row(lines[index]))
                        index += 1
                    return header, rows
        index += 1
    return [], []


def _column(header: list[str], *markers: str):
    for position, cell in enumerate(header):
        if any(marker in cell for marker in markers):
            return position
    return None


def _acceptance_vas(body: str, exempt: set[str]) -> list[dict]:
    """Parse the 视觉验收标准 table into per-VA check targets.

    Each VA binds a page/state/viewport cell, an axis and a blocking flag, so a
    visual failure can be re-verified for just the affected target instead of
    re-running every viewport.
    """
    header, rows = _table(body, '可观察标准', '检查轴')
    id_col = _column(header, 'ID')
    target_col = _column(header, '页面', '状态', '视口')
    axis_col = _column(header, '检查轴')
    blocking_col = _column(header, '阻断')
    if id_col is None or target_col is None or axis_col is None:
        return []
    vas = []
    for row in rows:
        if id_col >= len(row):
            continue
        ids = ID_TOKEN_RE.findall(row[id_col])
        if not ids:
            continue
        axis = row[axis_col].strip().strip('`').strip() if axis_col < len(row) else ''
        if axis not in VA_AXIS_VALUES:
            continue
        target = row[target_col].strip() if target_col < len(row) else ''
        blocking = False
        if blocking_col is not None and blocking_col < len(row):
            blocking = row[blocking_col].strip().strip('`').strip().lower() == 'yes'
        for vid in ids:
            vas.append({'id': vid, 'target': target, 'axis': axis,
                        'blocking': blocking, 'exempt': vid in exempt})
    return vas


def _va_parse_guard(lists: dict, body: str, vas: list[dict]) -> None:
    """Cross-check the contract's acceptance list against the parsed VA table.

    A table whose header drifted parses to zero rows while the JSON still names
    VAs; treating that as "no VAs" would silently weaken every axis rule that
    follows, so the disagreement is an error rather than an empty list.
    ``acceptance: []`` is legal: a contract need not declare any VA.
    """
    declared: list[str] = []
    for item in lists['acceptance']:
        declared.extend(re.findall(r'VA-\d+', item))
    if lists['acceptance'] and not declared:
        raise ValueError(
            'contract acceptance entries name no VA-<n> IDs: '
            + ', '.join(lists['acceptance'])
        )
    parsed = {va['id'] for va in vas}
    missing = sorted({vid for vid in declared if vid not in parsed})
    if missing:
        raise ValueError(
            'acceptance names VAs that the 视觉验收标准 table does not parse '
            '(missing or illegal axis): ' + ', '.join(missing)
        )
    if not declared and not vas and re.search(r'`VA-\d+`', body):
        raise ValueError(
            'the contract body mentions VA IDs but the 视觉验收标准 table parsed '
            'none; the table header or axis column has drifted'
        )


def read_contract_file(path: Path) -> tuple[str, dict, list[dict]]:
    """Return (contract_sha256, parsed_block, acceptance_vas) for a contract file."""
    if not path.is_file():
        raise ValueError(f'contract not found: {path}')
    text = path.read_text(encoding='utf-8')
    sha = _sha256_bytes(text.encode('utf-8'))
    data = _parse_contract_block(text)
    lists = _contract_lists(data)
    body = _strip_contract_block(text)
    exempt = set(lists['intentional_exceptions'])
    vas = _acceptance_vas(body, exempt)
    _va_parse_guard(lists, body, vas)
    return sha, data, vas


def _own_toolchain_root(root: Path) -> str | None:
    """The root-relative directory this script itself sits in, if any.

    The check skill stays in the fingerprint on purpose: a checker that can be
    softened mid-round would make its own PASS mean nothing. Naming the
    excluded directories instead of computing this one would turn that decision
    into a hardcoded exception that a rename silently breaks.
    """
    try:
        rel = Path(__file__).resolve().relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return None  # installed outside this project: nothing to carve out
    return rel.parts[0] if len(rel.parts) > 1 else None


def toolchain_dirs(root) -> tuple[str, ...]:
    """Root-relative directories holding the agent toolchain, minus the checker.

    Empty when no bundle is declared, so a project that does not ship one is
    fingerprinted exactly as before.
    """
    declaration = Path(root) / BUNDLE_DECLARATION
    if not declaration.is_file():
        return ()
    try:
        data = json.loads(declaration.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ()
    if not isinstance(data, dict):
        return ()
    skills = data.get('skills')
    if not isinstance(skills, dict):
        return ()
    declared = set()
    for details in skills.values():
        directory = details.get('directory') if isinstance(details, dict) else None
        if not isinstance(directory, str):
            continue
        directory = directory.strip().strip('/')
        if directory and '/' not in directory:
            declared.add(directory)
    declared.discard(_own_toolchain_root(root))
    return tuple(sorted(declared))


def _source_rule(rel_parts: tuple[str, ...], toolchain: tuple[str, ...] = ()) -> str | None:
    """Which ignore rule excludes a project-relative path, if any.

    Rules, narrowest first: bookkeeping directories at any depth, the declared
    toolchain directories at the project root, instruction and bundle files at
    the project root, runtime or build directories at the project root, and
    state-file suffixes anywhere.
    """
    if any(part in SOURCE_IGNORE for part in rel_parts):
        return 'tooling'
    if rel_parts and rel_parts[0] in toolchain:
        return 'tooling'
    if len(rel_parts) == 1 and rel_parts[0] in SOURCE_IGNORE_ROOT_FILES:
        return 'tooling'
    if toolchain and len(rel_parts) == 1 and rel_parts[0] in BUNDLE_ROOT_FILES:
        return 'tooling'
    if rel_parts and rel_parts[0] in SOURCE_IGNORE_ROOT:
        return 'runtime_or_build'
    if rel_parts and rel_parts[-1].endswith(SOURCE_IGNORE_SUFFIXES):
        return 'state_file'
    return None


def source_manifest(root) -> tuple[dict[str, str], list[str]]:
    """Fingerprint input for the working tree.

    Returns ``(rel_path -> sha256 hex of content, notable exclusions)``. Only
    paths excluded by a judgment about the project's shape are listed as
    exclusions: tooling directories are structural and would bury the signal,
    while a rule that swallowed product source is indistinguishable from a
    correct one unless it is reported.
    """
    root = Path(root)
    manifest: dict[str, str] = {}
    excluded: list[str] = []
    toolchain = toolchain_dirs(root)
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        rule = _source_rule(rel.parts, toolchain)
        if rule is not None:
            if rule != 'tooling':
                excluded.append(rel.as_posix())
            continue
        manifest[rel.as_posix()] = _sha256_bytes(path.read_bytes())
    return manifest, excluded


def _manifest_sha256(manifest: dict[str, str]) -> str:
    """Deterministic SHA-256 over an already-hashed path/content manifest.

    path (POSIX) + NUL + sha256(content) + LF, in sorted path order. Shared by
    the working-tree and git-tree scans so the two fingerprints are directly
    comparable, and by every diff, so a change list and a fingerprint can never
    disagree about what counts as source.
    """
    hasher = hashlib.sha256()
    found = False
    for rel in sorted(manifest):
        found = True
        hasher.update(rel.encode('utf-8'))
        hasher.update(b'\0')
        hasher.update(bytes.fromhex(manifest[rel]))
        hasher.update(b'\n')
    return hasher.hexdigest() if found else _sha256_bytes(b'')


def source_sha256(root) -> str:
    """SHA-256 over a deterministic manifest of project source files.

    The contract lives under .site and is excluded, so contract and source
    fingerprints move independently. Runtime state and build output are
    excluded too; :func:`plan` reports which paths that covered.
    """
    return _manifest_sha256(source_manifest(root)[0])


def _file_diff(prior: dict[str, str], current: dict[str, str]) -> dict:
    """Which files were added, removed or modified between two manifests."""
    added = sorted(set(current) - set(prior))
    removed = sorted(set(prior) - set(current))
    modified = sorted(rel for rel in set(prior) & set(current)
                      if prior[rel] != current[rel])
    truncated = any(len(items) > CHANGED_FILES_LIMIT
                    for items in (added, removed, modified))
    return {
        'added': added[:CHANGED_FILES_LIMIT],
        'removed': removed[:CHANGED_FILES_LIMIT],
        'modified': modified[:CHANGED_FILES_LIMIT],
        'truncated': truncated,
    }


def read_mode(root) -> str:
    """Project mode from .site/state.json, or 'guided' when there is no state.

    A missing state file is the quick path and stays guided. A state file that
    exists but cannot be read or does not carry a legal mode is an error: the
    old silent guided fallback let a strict project's corrupt state weaken the
    gate that report validation is for.
    """
    path = None
    for candidate in (Path(root) / STATE_REL_PATH, Path(root) / '.SITE/state.json', Path(root) / '.v3/state.json'):
        if candidate.is_file():
            path = candidate
            break
    if not path or not path.is_file():
        return 'guided'
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'state is unreadable: {exc}') from exc
    if not isinstance(state, dict):
        raise ValueError('state must be a JSON object')
    mode = state.get('mode')
    if mode not in ('guided', 'strict'):
        raise ValueError('state mode must be guided or strict')
    return mode


def required_axes(mode: str, vas: list[dict]) -> list[str]:
    """Axes a project must verify. Never drops below guided-core; when a scope
    boundary is ambiguous the floor (guided-core) wins rather than silently
    shrinking coverage."""
    axes = set(GUIDED_CORE)
    axes.add('negative_path')  # guided+: one most likely failure path
    for va in vas:
        if va['axis'] in AXES:
            axes.add(va['axis'])
    if mode == 'strict':
        axes.add('reopen')
        axes.add('risk')
    return [axis for axis in AXES if axis in axes]


def _git(root: Path, *args, stdin=None):
    """Run git in ``root`` without ever prompting. Returns (rc, stdout, stderr).

    Treats a missing git binary, timeouts, and other OS errors as "no git
    available" so callers can fall back to a conservative result instead of
    raising. Deterministic; never starts a browser.
    """
    env = {'GIT_TERMINAL_PROMPT': '0'}
    try:
        proc = subprocess.run(
            ['git', '-C', str(root), *args],
            capture_output=True, env=env, input=stdin, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 128, b'', b''
    return proc.returncode, proc.stdout, proc.stderr


def _git_repo_paths(root: Path):
    """Return (toplevel, prefix) if ``root`` is inside a git repo, else None.

    ``prefix`` is the path of ``root`` within the repo (with a trailing slash,
    possibly empty when ``root`` is the repo toplevel).
    """
    rc, out, _ = _git(root, 'rev-parse', '--show-toplevel', '--show-prefix')
    if rc != 0:
        return None
    lines = out.decode('utf-8', 'replace').splitlines()
    if len(lines) < 2:
        return None
    return lines[0], lines[1]


def _git_source_manifest(root: Path, ref: str, prefix: str):
    """Source manifest at ``ref``, mirroring :func:`source_manifest`.

    Materializes the tracked tree under the project subtree at ``ref`` via a
    single in-memory ``git archive`` (no disk extraction, no browser), applies
    the same ignore rules, and returns ``rel_path -> sha256 hex``. Returns
    ``None`` when the tree at ``ref`` is unreadable.
    """
    pathspec = ['--', prefix] if prefix else []
    rc, out, _ = _git(root, 'archive', '--format=tar', ref, *pathspec)
    if rc != 0 or not out:
        return None  # unreadable tree at ref → caller treats ref as unresolvable
    manifest: dict[str, str] = {}
    try:
        tar = tarfile.open(fileobj=io.BytesIO(out), mode='r:')
    except tarfile.TarError:
        return None
    with tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name
            if prefix and name.startswith(prefix):
                name = name[len(prefix):]
            name = name.lstrip('/')
            if not name:
                continue
            if _source_rule(tuple(Path(name).parts), toolchain_dirs(root)) is not None:
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            manifest[name] = _sha256_bytes(extracted.read())
    return manifest


def _git_source_sha256(root: Path, ref: str, prefix: str):
    """Source fingerprint at ``ref``; ``None`` when the tree is unreadable."""
    manifest = _git_source_manifest(root, ref, prefix)
    if manifest is None:
        return None
    # Mirror source_sha256(): an empty tree yields the empty manifest hash so
    # both sides stay directly comparable.
    return _manifest_sha256(manifest)


def _resolve_git_ref(root: Path, ref: str, contract_rel_to_root):
    """Resolve ``ref`` as a git revision and re-fingerprint at that revision.

    Returns a result dict (``resolved``, ``source='git'``, ``commit``,
    ``contract_sha256``, ``source_sha256``, ``source_manifest``) or ``None``
    when ``root`` is not in a git repo or ``ref`` does not resolve to a commit.
    The contract is read via ``git show``; when it is absent from the tree at
    ``ref`` (e.g. the contract was committed after that revision)
    ``contract_sha256`` is ``None``, which the caller treats conservatively as a
    contract change.
    """
    repo = _git_repo_paths(root)
    if repo is None:
        return None
    _toplevel, prefix = repo
    rc, out, _ = _git(root, 'rev-parse', '--verify', f'{ref}^{{commit}}')
    if rc != 0 or not out.strip():
        return None
    commit = out.decode('utf-8', 'replace').strip()
    prior_contract = None
    if contract_rel_to_root is not None:
        rc, out, _ = _git(root, 'show', f'{ref}:{prefix + contract_rel_to_root}')
        if rc == 0:
            prior_contract = _sha256_bytes(out)
        # rc != 0 means the contract is absent from the tree at ref (e.g. it
        # was committed after that revision); the caller conservatively treats
        # an absent contract as changed rather than silently dropping L0.
    prior_manifest = _git_source_manifest(root, ref, prefix)
    if prior_manifest is None:
        # The source tree at ref was unreadable; the ref is not safely
        # resolvable, so fall back to the conservative invalid-ref path.
        return None
    return {'resolved': True, 'source': 'git', 'commit': commit,
            'contract_sha256': prior_contract,
            'source_sha256': _manifest_sha256(prior_manifest),
            'source_manifest': prior_manifest, 'error': None}


def _read_source_manifest(data: dict):
    """A prior plan/report's own manifest, when it carries a usable one.

    Values must be 64-hex digests: a malformed manifest would otherwise diff as
    "every file modified", which reads like a real finding.
    """
    manifest = data.get('source_manifest')
    if not isinstance(manifest, dict) or not manifest:
        return None
    for key, value in manifest.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return None
        if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            return None
    return manifest


def _resolve_prior(ref: str, root: Path, contract_rel_to_root):
    """Resolve a ``--changed-from`` REF into prior fingerprints.

    REF is interpreted without ambiguity:

      * a path to a readable JSON plan/report carrying ``contract_sha256``
        and/or ``source_sha256`` — those fingerprints are reused as-is (and its
        ``source_manifest`` when present, so the change list stays available); or
      * a git revision (branch / tag / commit) resolvable in the project's
        repository — the contract and source tree are re-fingerprinted at that
        revision so they are directly comparable to the current plan.

    Returns a dict with ``resolved`` (False when REF is neither), the prior
    fingerprints, and an ``error`` string explaining why when unresolvable.
    """
    path = Path(ref)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict) and (
                'contract_sha256' in data or 'source_sha256' in data):
            return {'resolved': True, 'source': 'json', 'commit': None,
                    'contract_sha256': data.get('contract_sha256'),
                    'source_sha256': data.get('source_sha256'),
                    'source_manifest': _read_source_manifest(data), 'error': None}
        # A readable file that is not a usable report/plan: fall through to git
        # so a stray file never silently zeroes the invalidation scope.
    git_result = _resolve_git_ref(root, ref, contract_rel_to_root)
    if git_result is not None:
        return git_result
    return {'resolved': False, 'source': None, 'commit': None,
            'contract_sha256': None, 'source_sha256': None,
            'source_manifest': None,
            'error': f'ref is neither a readable JSON report/plan nor a '
                     f'resolvable git revision: {ref}'}


def plan(root, contract_rel: str | None = None, changed_from: str | None = None) -> dict:
    root = Path(root).resolve()
    if contract_rel is None:
        contract_file = contract_path(root)
        try:
            contract_rel = contract_file.relative_to(root).as_posix()
        except ValueError:
            contract_rel = str(contract_file)
    else:
        contract_file = Path(contract_rel) if Path(contract_rel).is_absolute() else root / contract_rel
    sha, _data, vas = read_contract_file(contract_file)
    mode = read_mode(root)
    manifest, excluded = source_manifest(root)
    src_sha = _manifest_sha256(manifest)
    required = required_axes(mode, vas)

    changed = None
    if changed_from:
        try:
            contract_rel_to_root = contract_file.relative_to(root).as_posix()
        except ValueError:
            contract_rel_to_root = None  # contract outside root; git can't see it
        prior = _resolve_prior(changed_from, root, contract_rel_to_root)
        if not prior['resolved']:
            # Invalid REF: stay machine-readable. The plan reports that it could
            # not tell what changed instead of guessing a scope; the report gate
            # still refuses any report whose fingerprints do not match this tree.
            changed = {
                'ref': changed_from,
                'available': False,
                'error': prior.get('error'),
                'changed_files': None,
            }
        else:
            prior_contract = prior['contract_sha256']
            prior_source = prior['source_sha256']
            if prior['source'] == 'git':
                # Git re-fingerprinted the tree at ref. A contract/source that
                # is absent at ref but present now was added since ref, so treat
                # absence conservatively as a change rather than silently
                # dropping the affected levels.
                contract_changed = prior_contract is None or prior_contract != sha
                source_changed = prior_source is None or prior_source != src_sha
            else:  # JSON report/plan: only compare fields it actually recorded
                contract_changed = prior_contract is not None and prior_contract != sha
                source_changed = prior_source is not None and prior_source != src_sha
            prior_manifest = prior.get('source_manifest')
            changed = {
                'ref': changed_from,
                'available': True,
                'source': prior['source'],
                'commit': prior.get('commit'),
                'contract_changed': contract_changed,
                'source_changed': source_changed,
                # The fact this plan exists to report. What to re-verify is the
                # agent's call: a file→axis map would be a guess (see docstring).
                'changed_files': (_file_diff(prior_manifest, manifest)
                                  if prior_manifest is not None else None),
            }
            if prior_manifest is None:
                changed['changed_files_note'] = (
                    'this REF records only aggregate fingerprints; for a '
                    'per-file change list use a git revision or a plan/report '
                    'that carries source_manifest'
                )

    return {
        'project_root': str(root),
        'mode': mode,
        'contract_path': contract_rel,
        'contract_sha256': sha,
        'source_sha256': src_sha,
        'source_files': len(manifest),
        'source_excluded': excluded[:SOURCE_EXCLUDED_LIMIT],
        'source_excluded_truncated': len(excluded) > SOURCE_EXCLUDED_LIMIT,
        'source_manifest': manifest,
        'levels': [dict(level) for level in LEVELS],
        'required_axes': required,
        'acceptance': vas,
        'rules': {
            'browser_blocked_below': 'L1',
            'static_failure_blocks_browser': True,
            'visual_reverify_scope': 'affected_va_only',
            'contract_change_invalidates': list(AXES),
            'source_change_invalidates': list(SOURCE_INVALIDATES),
            'guided_allows_limited': True,
            'strict_requires_independent_verified': True,
        },
        'changed_from': changed,
        'generated_at': now(),
    }


def _axis_status(axes: dict, axis: str) -> str | None:
    result = axes.get(axis)
    if not isinstance(result, dict):
        return None
    status = result.get('status')
    return status if status in VERIFY_STATUSES else None


def _string_list(value, field: str, errors: list[str]) -> list[str]:
    """A report list field must be a list of non-empty strings.

    Returning ``[]`` on a malformed value silently turned "no evidence" into a
    valid-looking empty list; appending an error keeps the malformed shape
    visible to whoever reads the report.
    """
    if not isinstance(value, list):
        errors.append(f'{field} must be a list')
        return []
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(f'{field} entries must be non-empty strings')
            continue
        cleaned.append(item)
    return cleaned


def validate_report(root, report_path) -> dict:
    """Check a report against the protocol for the tree as it is right now.

    Fingerprints are an identity check, not a re-run schedule: a report whose
    ``contract_sha256``/``source_sha256`` differ from the current tree is not
    valid and cannot be re-scoped into validity. The answer is a fresh report
    for the current tree, with any axis that was not re-run reported honestly
    as ``limited``. A report that still reuses an earlier tree's fingerprints
    is the failure this gate exists to catch.
    """
    root = Path(root).resolve()
    try:
        report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        return {'project_root': str(root), 'valid': False,
                'errors': [f'report unreadable: {exc}']}
    if not isinstance(report, dict):
        return {'project_root': str(root), 'valid': False,
                'errors': ['report must be a JSON object']}

    errors: list[str] = []
    reported_root = report.get('project_root')
    # An absent/empty project_root resolves to the CWD; running from inside the
    # project would then match by accident and validate a report that names no
    # project at all.
    if not isinstance(reported_root, str) or not reported_root.strip():
        errors.append('project_root is missing')
    elif Path(reported_root).resolve() != root:
        errors.append('project_root does not match')
    mode = report.get('mode')
    if mode not in ('guided', 'strict'):
        errors.append('mode must be guided or strict')
    # One-way cross-check: a strict project must never accept a guided report.
    # The reverse is fine -- a report may have been written before the project
    # switched to strict, and re-running it is the agent's call.
    try:
        project_mode = read_mode(root)
    except (OSError, ValueError) as exc:
        errors.append(f'project state is unreadable: {exc}')
    else:
        if project_mode == 'strict' and mode != 'strict':
            errors.append('project state is strict but the report mode is not strict')
    overall = report.get('overall')
    if overall not in DELIVERABLE_STATUSES:
        errors.append('overall must be verified, limited or blocked')

    # Current fingerprints. A report is only ever a statement about one tree,
    # so when the contract cannot be read the fingerprints cannot be compared
    # and the report cannot be validated -- skipping the comparison here used
    # to accept any stale report once the contract file was gone, which turned
    # a missing spec into a passing delivery.
    required: list[str] = []
    contract_ok = source_ok = None
    excluded: list[str] = []
    try:
        cur_contract, _data, vas = read_contract_file(contract_path(root))
    except (OSError, ValueError) as exc:
        errors.append(f'contract is missing or unreadable: {exc}')
    else:
        try:
            manifest, excluded = source_manifest(root)
        except (OSError, ValueError) as exc:
            errors.append(f'source tree is unreadable: {exc}')
        else:
            cur_source = _manifest_sha256(manifest)
            contract_ok = report.get('contract_sha256') == cur_contract
            source_ok = report.get('source_sha256') == cur_source
            if mode in ('guided', 'strict'):
                required = required_axes(mode, vas)

    axes = report.get('axes')
    if not isinstance(axes, dict):
        errors.append('axes must be an object')
        axes = {}

    # Gating: an L0/L1 failure -- blocked or not_run -- must not start the
    # browser. A static gate that did not run is not a passed gate.
    static_failed = any(_axis_status(axes, a) in ('blocked', 'not_run')
                        for a in STATIC_AXES)
    browser_blocked = static_failed
    if static_failed:
        for a in BROWSER_AXES:
            status = _axis_status(axes, a)
            if status in ('verified', 'limited', 'blocked'):
                errors.append(f'{a} must be not_run when a static gate failed')

    # Required axes must be present with a valid status.
    for a in required:
        if _axis_status(axes, a) is None:
            errors.append(f'{a} missing or invalid status')

    # An axis that claims success has to say what it looked at. This is for
    # whoever reads the report next, not a check on whether it is true: no
    # field can carry that, and a field that claims to is worse than none.
    for a in AXES:
        result = axes.get(a)
        if not isinstance(result, dict) or result.get('status') != 'verified':
            continue
        observed = result.get('observed')
        if not isinstance(observed, str) or not observed.strip():
            errors.append(f'{a} verified without recording what was observed')

    # failed_vas must be a list of non-empty VA ids on every axis that carries
    # it: a string would be iterated character by character and a non-string
    # entry would land in reverify_vas as-is.
    failed_vas_by_axis: dict[str, list[str]] = {}
    for axis in AXES:
        result = axes.get(axis)
        if not isinstance(result, dict) or 'failed_vas' not in result:
            continue
        failed = result.get('failed_vas')
        if not isinstance(failed, list):
            errors.append(f'{axis} failed_vas must be a list')
            continue
        cleaned: list[str] = []
        for vid in failed:
            if not isinstance(vid, str) or not vid.strip():
                errors.append(f'{axis} failed_vas entries must be non-empty strings')
                continue
            cleaned.append(vid)
        failed_vas_by_axis[axis] = cleaned

    # Re-verification scope: failures invalidate their dependents; visual
    # failures scope to the affected VA only. Hash-invalidated axes are added
    # wholesale. The scope is bounded by what the project actually requires.
    invalidated: list[str] = []
    if contract_ok is not None and source_ok is not None:
        if not contract_ok:
            invalidated = list(AXES)
        elif not source_ok:
            invalidated = list(SOURCE_INVALIDATES)
    reverify: set[str] = set(invalidated)
    reverify_vas: list[dict] = []
    required_set = set(required)
    for axis in AXES:
        if _axis_status(axes, axis) != 'blocked':
            continue
        if axis in required_set or axis in invalidated:
            reverify.add(axis)
        dependents = DEPENDENTS.get(axis)
        if dependents is None:
            dependents = list(GUIDED_CORE)
        for dep in dependents:
            if dep in required_set:
                reverify.add(dep)
        if axis in ('visual_desktop', 'visual_mobile'):
            for vid in failed_vas_by_axis.get(axis, []):
                reverify_vas.append({'axis': axis, 'va': vid})

    raw_independent = report.get('independent', False)
    if not isinstance(raw_independent, bool):
        # JSON has a boolean type; a string like "false" is not it. Treating
        # the non-empty string as True would let a guided report claim the
        # strict independent gate by accident.
        errors.append('independent must be a JSON boolean')
        independent = False
    else:
        independent = raw_independent
    evidence = _string_list(report.get('evidence', []), 'evidence', errors)
    limitations = _string_list(report.get('limitations', []), 'limitations', errors)
    if overall == 'limited' and not limitations:
        errors.append('limited overall requires limitations')
    if not evidence:
        # Every deliverable status names what it looked at; a blocked report
        # without evidence leaves the blocker unknown to whoever resumes.
        errors.append('overall requires at least one evidence item')
    if mode == 'strict':
        if overall == 'limited':
            errors.append('strict mode cannot be delivered with limited')
        if overall == 'verified' and not independent:
            errors.append('strict mode requires independent verification')

    # Overall must agree with the worst required-axis status.
    if required:
        statuses = [_axis_status(axes, a) for a in required]
        if any(s == 'blocked' for s in statuses):
            computed = 'blocked'
        elif any(s == 'limited' for s in statuses):
            computed = 'limited'
        elif all(s == 'verified' for s in statuses):
            computed = 'verified'
        else:
            computed = 'blocked'  # not_run / missing cannot deliver
        if computed != overall:
            errors.append(f'overall {overall} does not match axis results ({computed})')

    valid = not errors and not invalidated
    return {
        'project_root': str(root),
        'valid': valid,
        'mode': mode,
        'overall': overall,
        'independent': independent,
        'hash': {'contract_valid': contract_ok, 'source_valid': source_ok},
        'invalidated_axes': invalidated,
        'reverify': [a for a in AXES if a in reverify],
        'reverify_vas': reverify_vas,
        'browser_blocked': browser_blocked,
        'errors': errors,
    }


def _plan_summary(result: dict, report_path=None) -> dict:
    """Bounded stdout view of a plan: counts, fingerprints and axes, no manifest.

    A plan carries one manifest entry per source file, so printing it verbatim
    scales with the project. ``--summary`` keeps stdout to what the caller acts
    on and leaves the manifest in ``--out``.
    """
    excluded = result.get('source_excluded') or []
    changed = result.get('changed_from')
    if isinstance(changed, dict):
        files = changed.get('changed_files')
        changed = {key: changed.get(key) for key in
                   ('ref', 'available', 'source', 'commit',
                    'contract_changed', 'source_changed', 'error',
                    'changed_files_note')}
        if isinstance(files, dict):
            changed['changed_file_counts'] = {
                key: len(files.get(key) or [])
                for key in ('added', 'removed', 'modified')}
            changed['changed_files_truncated'] = bool(files.get('truncated'))
    return {
        'mode': 'summary',
        'project_root': result.get('project_root'),
        'project_mode': result.get('mode'),
        'contract_path': result.get('contract_path'),
        'contract_sha256': result.get('contract_sha256'),
        'source_sha256': result.get('source_sha256'),
        'source_files': result.get('source_files'),
        'source_excluded_count': len(excluded),
        'source_excluded_truncated': result.get('source_excluded_truncated', False),
        'required_axes': result.get('required_axes'),
        'changed_from': changed,
        'generated_at': result.get('generated_at'),
        'note': 'manifest omitted; use --out <path> for the complete plan',
        'report': str(report_path) if report_path else None,
    }


def _emit_plan(args, result: dict) -> None:
    """Write the complete plan when --out is given, then print it or its summary."""
    text = json.dumps(result, ensure_ascii=False, indent=2)
    report_path = None
    if args.out:
        report_path = args.out.expanduser()
        report_path.write_text(text + '\n', encoding='utf-8')
        report_path = report_path.resolve()
    if args.summary:
        print(json.dumps(_plan_summary(result, report_path),
                         ensure_ascii=False, indent=2))
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    plan_p = sub.add_parser('plan', help='generate a verification plan from the project contract')
    plan_p.add_argument('root', type=Path, help='project root')
    plan_p.add_argument('--contract', default=None,
                        help='contract path relative to the project root '
                             '(default: auto-detect .site/design/surface-brief.md)')
    plan_p.add_argument('--changed-from', default=None,
                        help='a prior plan/report JSON path OR a git revision '
                             '(branch/tag/commit) to diff fingerprints against; '
                             'an REF that is neither is reported and conservatively '
                             'upgrades to guided-core')
    plan_p.add_argument('--out', type=Path,
                        help='write the complete plan JSON to this path as well as stdout')
    plan_p.add_argument('--summary', action='store_true',
                        help='print a bounded summary (counts, fingerprints and axes; '
                             'no manifest) instead of the full plan; --out still '
                             'receives the complete plan')

    val_p = sub.add_parser('validate-report', help='validate a check report against the protocol')
    val_p.add_argument('root', type=Path, help='project root')
    val_p.add_argument('report', type=Path, help='check report JSON to validate')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == 'plan':
            _emit_plan(args, plan(args.root, args.contract, args.changed_from))
            return 0
        result = validate_report(args.root, args.report)
    except (OSError, ValueError, json.JSONDecodeError, AttributeError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
