#!/usr/bin/env python3
"""Lightweight, deterministic check protocol for site-check.

Generates a verification plan and validates check reports against the check protocol.
It never starts a browser: it only reads the contract and source,
computes SHA-256 fingerprints, and checks that a report conforms to the
gating, dependency, hash-invalidation and mode rules. Python 3.10+, stdlib only.

The protocol is organized in six levels (L0-L5) over eight axes:

    L0  contract          static, no browser
    L1  static_build      static, no browser
    L2  core_task         browser
    L3  negative_path     browser
    L4  visual_desktop / visual_mobile   browser, per viewport
    L5  reopen / risk     browser

Rules encoded here:
  * L0/L1 failure does not start the browser; browser axes must be ``not_run``.
  * A visual failure only re-verifies the affected page/state/viewport (VA),
    not every viewport; failed VAs are carried in the report.
  * A contract SHA-256 change invalidates every axis; a source SHA-256 change
    invalidates L1-L5 (the contract lives under ``.site`` and is hashed
    separately, so L0 stays valid when only source changes).
  * guided may honestly report ``limited``; strict cannot be ``limited`` and a
    strict ``verified`` requires independent verification.
  * When an axis dependency is ambiguous, the scope escalates to guided-core
    (contract + static_build + core_task) rather than silently shrinking.
  * --changed-from REF accepts two kinds of input with no ambiguity: a path to
    a prior check-report.json or a git commit reference (e.g. HEAD~1).
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

SOURCE_IGNORE = {'.site', '.SITE', '.v3', '.git', 'node_modules', '__pycache__', '.DS_Store'}


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
    return sha, data, vas


def _iter_source_files(root: Path):
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SOURCE_IGNORE for part in rel.parts):
            continue
        yield path


def _manifest_sha256(entries) -> str:
    """Deterministic SHA-256 over (rel_path, content) pairs, sorted by path.

    Shared by the working-tree and git-tree source scans so the two
    fingerprints are directly comparable: path (POSIX) + NUL + sha256(content)
    + LF, in sorted path order.
    """
    hasher = hashlib.sha256()
    found = False
    for rel, content in sorted(entries, key=lambda e: e[0]):
        found = True
        hasher.update(rel.encode('utf-8'))
        hasher.update(b'\0')
        hasher.update(hashlib.sha256(content).digest())
        hasher.update(b'\n')
    return hasher.hexdigest() if found else _sha256_bytes(b'')


def source_sha256(root) -> str:
    """SHA-256 over a deterministic manifest of project source files.

    The contract lives under .site and is excluded, so contract and source
    fingerprints move independently.
    """
    root = Path(root)
    entries = []
    for path in _iter_source_files(root):
        rel = path.relative_to(root).as_posix()
        entries.append((rel, path.read_bytes()))
    return _manifest_sha256(entries)


def read_mode(root) -> str:
    """Project mode from .site/state.json, or 'guided' when there is no state."""
    path = None
    for candidate in (Path(root) / STATE_REL_PATH, Path(root) / '.SITE/state.json', Path(root) / '.v3/state.json'):
        if candidate.is_file():
            path = candidate
            break
    if not path or not path.is_file():
        return 'guided'
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return 'guided'
    mode = state.get('mode')
    return mode if mode in ('guided', 'strict') else 'guided'


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


def _git_source_sha256(root: Path, ref: str, prefix: str):
    """Source manifest at ``ref``, mirroring :func:`source_sha256`.

    Materializes the tracked tree under the project subtree at ``ref`` via a
    single in-memory ``git archive`` (no disk extraction, no browser), applies
    the same ignore rules, and reuses :func:`_manifest_sha256` so the result is
    directly comparable to the working-tree fingerprint. Returns ``None`` when
    no source files exist at ``ref``.
    """
    pathspec = ['--', prefix] if prefix else []
    rc, out, _ = _git(root, 'archive', '--format=tar', ref, *pathspec)
    if rc != 0 or not out:
        return None  # unreadable tree at ref → caller treats ref as unresolvable
    entries = []
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
            if any(part in SOURCE_IGNORE for part in Path(name).parts):
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            entries.append((name, extracted.read()))
    # Mirror source_sha256(): an empty tree yields the empty manifest hash so
    # both sides stay directly comparable.
    return _manifest_sha256(entries)


def _resolve_git_ref(root: Path, ref: str, contract_rel_to_root):
    """Resolve ``ref`` as a git revision and re-fingerprint at that revision.

    Returns a result dict (``resolved``, ``source='git'``, ``commit``,
    ``contract_sha256``, ``source_sha256``) or ``None`` when ``root`` is not in
    a git repo or ``ref`` does not resolve to a commit. The contract is read
    via ``git show``; when it is absent from the tree at ``ref`` (e.g. the
    contract was committed after that revision) ``contract_sha256`` is ``None``,
    which the caller treats conservatively as a contract change.
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
    prior_source = _git_source_sha256(root, ref, prefix)
    if prior_source is None:
        # The source tree at ref was unreadable; the ref is not safely
        # resolvable, so fall back to the conservative invalid-ref path.
        return None
    return {'resolved': True, 'source': 'git', 'commit': commit,
            'contract_sha256': prior_contract, 'source_sha256': prior_source,
            'error': None}


def _resolve_prior(ref: str, root: Path, contract_rel_to_root):
    """Resolve a ``--changed-from`` REF into prior fingerprints.

    REF is interpreted without ambiguity:

      * a path to a readable JSON plan/report carrying ``contract_sha256``
        and/or ``source_sha256`` — those fingerprints are reused as-is; or
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
                    'source_sha256': data.get('source_sha256'), 'error': None}
        # A readable file that is not a usable report/plan: fall through to git
        # so a stray file never silently zeroes the invalidation scope.
    git_result = _resolve_git_ref(root, ref, contract_rel_to_root)
    if git_result is not None:
        return git_result
    return {'resolved': False, 'source': None, 'commit': None,
            'contract_sha256': None, 'source_sha256': None,
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
    src_sha = source_sha256(root)
    required = required_axes(mode, vas)

    changed = None
    if changed_from:
        try:
            contract_rel_to_root = contract_file.relative_to(root).as_posix()
        except ValueError:
            contract_rel_to_root = None  # contract outside root; git can't see it
        prior = _resolve_prior(changed_from, root, contract_rel_to_root)
        if not prior['resolved']:
            # Invalid REF: stay machine-readable AND conservative. The protocol
            # never silently shrinks coverage when a dependency is ambiguous, so
            # upgrade to the guided-core floor rather than claiming nothing
            # changed.
            changed = {
                'ref': changed_from,
                'available': False,
                'error': prior.get('error'),
                'invalidated_axes': list(GUIDED_CORE),
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
            if contract_changed:
                invalidated = list(AXES)
            elif source_changed:
                invalidated = list(SOURCE_INVALIDATES)
            else:
                invalidated = []
            changed = {
                'ref': changed_from,
                'available': True,
                'source': prior['source'],
                'commit': prior.get('commit'),
                'contract_changed': contract_changed,
                'source_changed': source_changed,
                'invalidated_axes': invalidated,
            }

    return {
        'project_root': str(root),
        'mode': mode,
        'contract_path': contract_rel,
        'contract_sha256': sha,
        'source_sha256': src_sha,
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


def validate_report(root, report_path) -> dict:
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
    if Path(str(report.get('project_root', ''))).resolve() != root:
        errors.append('project_root does not match')
    mode = report.get('mode')
    if mode not in ('guided', 'strict'):
        errors.append('mode must be guided or strict')
    overall = report.get('overall')
    if overall not in DELIVERABLE_STATUSES:
        errors.append('overall must be verified, limited or blocked')

    # Current fingerprints; if the contract is unreadable the hash check is
    # skipped (it cannot prove or disprove the report on its own).
    required: list[str] = []
    contract_ok = source_ok = None
    try:
        cur_contract, _data, vas = read_contract_file(contract_path(root))
        cur_source = source_sha256(root)
        contract_ok = report.get('contract_sha256') == cur_contract
        source_ok = report.get('source_sha256') == cur_source
        if mode in ('guided', 'strict'):
            required = required_axes(mode, vas)
    except (OSError, ValueError):
        pass

    invalidated: list[str] = []
    if contract_ok is not None and source_ok is not None:
        if not contract_ok:
            invalidated = list(AXES)
        elif not source_ok:
            invalidated = list(SOURCE_INVALIDATES)

    axes = report.get('axes')
    if not isinstance(axes, dict):
        errors.append('axes must be an object')
        axes = {}

    # Gating: an L0/L1 failure must not start the browser.
    static_failed = any(_axis_status(axes, a) == 'blocked' for a in STATIC_AXES)
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

    # Re-verification scope: failures invalidate their dependents; visual
    # failures scope to the affected VA only. Hash-invalidated axes are added
    # wholesale. The scope is bounded by what the project actually requires.
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
            result = axes.get(axis) or {}
            for vid in result.get('failed_vas', []) or []:
                reverify_vas.append({'axis': axis, 'va': vid})

    independent = bool(report.get('independent', False))
    evidence = report.get('evidence', [])
    limitations = report.get('limitations', [])
    if not isinstance(evidence, list):
        evidence = []
    if not isinstance(limitations, list):
        limitations = []
    if overall == 'limited' and not limitations:
        errors.append('limited overall requires limitations')
    if overall in ('verified', 'limited') and not evidence:
        errors.append('verified/limited overall requires evidence')
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    plan_p = sub.add_parser('plan', help='generate a verification plan from the project contract')
    plan_p.add_argument('root', type=Path, help='project root')
    plan_p.add_argument('--contract', default=CONTRACT_REL_PATH,
                        help='contract path relative to the project root')
    plan_p.add_argument('--changed-from', default=None,
                        help='a prior plan/report JSON path OR a git revision '
                             '(branch/tag/commit) to diff fingerprints against; '
                             'an REF that is neither is reported and conservatively '
                             'upgrades to guided-core')

    val_p = sub.add_parser('validate-report', help='validate a check report against the protocol')
    val_p.add_argument('root', type=Path, help='project root')
    val_p.add_argument('report', type=Path, help='check report JSON to validate')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == 'plan':
            result = plan(args.root, args.contract, args.changed_from)
        else:
            result = validate_report(args.root, args.report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
