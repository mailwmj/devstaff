"""Static, command and matrix checks for collaborative site skills. Python 3.10+, standard library only.

Every run gets a ``check_id`` and, when the project has ``.site`` metadata, is
persisted under ``.site/checks/<check_id>.json`` together with the source
fingerprint.  ``site-builder`` accepts delivery only through a ``matrix``
artifact whose fingerprint still matches the frozen source. ``check_id`` is the
SHA-256 of canonical artifact content (excluding its derived id/path), so accidental
edits are detected on every load. This is tamper-evident bookkeeping, not a signature
or a defense against an agent that can rewrite the whole project.

The matrix does not take a bare ``evidence`` sentence.  Each item declares
where its evidence comes from:

``artifact``
    Named files (screenshots, JSON/HTML results, logs) that exist inside the
    project.  Their sha256 is recorded, so delivery can prove they were not
    edited after the check.
``command``
    ``check_id`` values of earlier ``check.py run`` results that exited 0 and
    match the current source.
``observation``
    Machine-usable result from something that cannot be archived, e.g. reading
    a clipboard by hand.
``declared``
    A claim only.  It is recorded for the report but never counts as evidence,
    so it is refused for blocking items.

Only ``artifact`` and ``command`` may carry a blocking item; anything else has
to be reported as ``not_run`` instead of ``passed``.

Every matrix needs a non-empty ``profile_reason`` and an ``axis`` on each item.
Full verification requires blocking static/build, core-task, desktop visual,
mobile visual and reopening axes; narrower profiles still require a blocking
affected core task.

The profile is not a free choice.  Each matrix declares ``consequence`` (would a
wrong result hurt the user: a missed train, lost money, leaked data) and
``surface`` (how far the change reaches), and the tool derives the only profile
that round may use.  ``full`` is reserved for high-consequence changes that also
reach wide, so cosmetic polish can never buy a full re-verification.

Archived evidence is budgeted rather than merely allowed: at most
``EVIDENCE_BUDGET_PER_ITEM`` files per item and ``EVIDENCE_BUDGET_TOTAL`` for the
whole matrix, because a folder of screenshots is not a conclusion.

Small fixes may re-verify only the affected items and carry the rest with
``carried_from`` (a prior ``check_id``).  Narrow profiles only; the tool proves
the link and the disclosure, never that the change left the item untouched.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SKIP = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', '.next', '.cache'}
CHECK_STATUSES = ('passed', 'failed', 'not_run', 'not_applicable')
CHECK_ARTIFACT_DIR = 'checks'
CHECK_PROFILES = ('smoke', 'targeted', 'full')
CHECK_CONSEQUENCES = ('high', 'low')
CHECK_SURFACES = ('narrow', 'wide')
FULL_REQUIRED_AXES = ('static_build', 'core_task', 'visual_desktop', 'visual_mobile', 'reopen')
EVIDENCE_KINDS = ('artifact', 'command', 'observation', 'declared')
DEFAULT_EVIDENCE_KIND = 'declared'
VERIFIABLE_EVIDENCE_KINDS = ('artifact', 'command')
PATH_KEYS = ('paths', 'artifacts', 'files', 'screenshots')
CARRY_PROFILES = ('smoke', 'targeted')
EVIDENCE_BUDGET_PER_ITEM = 3
EVIDENCE_BUDGET_TOTAL = 24


def now():
    return datetime.now(timezone.utc).isoformat()


def files(root):
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(
            name for name in dirs
            if name not in SKIP and not name.startswith('.') and not Path(directory, name).is_symlink()
        )
        for name in sorted(names):
            path = Path(directory, name)
            if name != '.DS_Store' and not path.is_symlink():
                yield path


def fingerprint(root):
    digest = hashlib.sha256()
    paths = list(files(root))
    metadata = root / '.site'
    if metadata.is_symlink():
        raise ValueError('Project metadata must not be a symlink')
    design = metadata / 'design'
    if design.exists() and (design.is_symlink() or not design.is_dir()):
        raise ValueError('Project design metadata must be a regular directory')
    if design.is_dir():
        paths.extend(path for path in files(design) if path.is_file())
    for name in ('brief.md', 'implementation-plan.md', 'contract.md', 'work.md', 'preview.py'):
        path = metadata / name
        if path.is_file() and not path.is_symlink():
            paths.append(path)
    for path in sorted(set(paths)):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def artifact_digest(data):
    canonical = {
        key: value for key, value in data.items()
        if key not in ('check_id', 'artifact')
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def validate_artifact_identity(artifact, check_id, path):
    if artifact.get('check_id') != check_id or path.stem != check_id:
        raise ValueError(f'Damaged check artifact {check_id!r}: filename and internal check_id differ')
    if artifact_digest(artifact) != check_id:
        raise ValueError(f'Damaged check artifact {check_id!r}: content digest does not match check_id')
    expected = f'.site/{CHECK_ARTIFACT_DIR}/{check_id}.json'
    if artifact.get('artifact') != expected:
        raise ValueError(f'Damaged check artifact {check_id!r}: artifact path does not match its filename')


def write_artifact(root, data):
    """Persist the evidence under .site/checks/ so site-builder can bind delivery to it.

    Projects without .site metadata are left untouched: this tool never initializes
    or rewrites a third-party project.
    """
    metadata = root / '.site'
    if metadata.is_symlink() or not metadata.is_dir():
        return None
    folder = metadata / CHECK_ARTIFACT_DIR
    if folder.is_symlink():
        raise ValueError('Check artifact directory must not be a symlink')
    folder.mkdir(exist_ok=True)
    path = folder / f"{data['check_id']}.json"
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=folder, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        temporary = handle.name
    os.replace(temporary, path)
    return path.relative_to(root).as_posix()


def finalize(root, data):
    data.pop('check_id', None)
    data.pop('artifact', None)
    data.pop('artifact_note', None)
    metadata = root / '.site'
    persists = metadata.is_dir() and not metadata.is_symlink()
    if not persists:
        data['artifact'] = None
        data['artifact_note'] = 'No .site metadata; the evidence was reported but not persisted'
    data['check_id'] = artifact_digest(data)
    if persists:
        data['artifact'] = f'.site/{CHECK_ARTIFACT_DIR}/{data["check_id"]}.json'
        data['artifact'] = write_artifact(root, data)
    return data


def artifact_rows(root, values):
    """Resolve declared evidence paths inside the project and hash them."""
    rows, problems = [], []
    for raw in values:
        if not isinstance(raw, str) or not raw.strip():
            problems.append('artifact path must be a non-empty string')
            continue
        candidate = Path(raw.strip()).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        relative = os.path.relpath(resolved, root)
        if relative.startswith('..'):
            problems.append(f'artifact outside the project: {raw}')
            continue
        display = Path(relative).as_posix()
        if candidate.is_symlink():
            problems.append(f'artifact must not be a symlink: {display}')
            continue
        if not resolved.is_file():
            problems.append(f'artifact does not exist: {display}')
            continue
        try:
            data = resolved.read_bytes()
        except OSError as error:
            problems.append(f'artifact cannot be read: {display} ({error})')
            continue
        rows.append({'path': display, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
    return rows, problems


def load_check_artifact(root, check_id):
    if not isinstance(check_id, str) or not check_id.strip():
        raise ValueError('command evidence needs a non-empty check_id')
    check_id = check_id.strip()
    if any(part in check_id for part in ('/', '\\', '..')):
        raise ValueError(f'check_id must be a plain identifier: {check_id!r}')
    path = root / '.site' / CHECK_ARTIFACT_DIR / f'{check_id}.json'
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'No stored check artifact for check_id {check_id!r}')
    try:
        artifact = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        raise ValueError(f'Damaged check artifact {check_id!r}: {error}') from error
    if not isinstance(artifact, dict):
        raise ValueError(f'Damaged check artifact {check_id!r}')
    validate_artifact_identity(artifact, check_id, path)
    return artifact


def validate_evidence(root, item, identifier, current, cache, carried=False):
    """Return (evidence, artifacts, problem) for one matrix item.

    ``carried`` marks an item whose conclusion comes from an earlier round.  Its
    archived evidence must still exist and be unchanged, but a stored command
    result is allowed to belong to the earlier source, because the whole point
    of carrying is that the source has moved on.
    """
    raw = item.get('evidence')
    if isinstance(raw, dict):
        kind = str(raw.get('kind') or DEFAULT_EVIDENCE_KIND).strip().lower()
        summary = str(raw.get('summary') or '').strip()
        paths = [value for key in PATH_KEYS for value in (raw.get(key) or [])]
        commands = list(raw.get('commands') or [])
    elif isinstance(raw, str) and raw.strip():
        kind, summary, paths, commands = DEFAULT_EVIDENCE_KIND, raw.strip(), [], []
    else:
        raise ValueError(
            f"Matrix item {identifier!r} needs evidence; use an object with kind "
            f"{EVIDENCE_KINDS} plus summary/paths/commands, or a plain summary string"
        )
    if kind not in EVIDENCE_KINDS:
        raise ValueError(f'Matrix item {identifier!r} evidence kind must be one of {EVIDENCE_KINDS}, got {kind!r}')
    if item['blocking'] and kind not in VERIFIABLE_EVIDENCE_KINDS:
        raise ValueError(
            f'Matrix item {identifier!r} is blocking but its evidence kind is {kind!r}; '
            'blocking items need artifact or command evidence, otherwise report not_run'
        )
    entries, problems = [], []
    for value in paths:
        key = str(value)
        if key not in cache:
            cache[key] = artifact_rows(root, [value])
        rows, issue = cache[key]
        entries.extend(rows)
        problems.extend(issue)
    for check_id in commands:
        artifact = load_check_artifact(root, check_id)
        if artifact.get('kind') != 'command':
            problems.append(f'command evidence {check_id!r} is a {artifact.get("kind")!r} artifact, not a command result')
            continue
        if artifact.get('exit_code') != 0:
            problems.append(f'command evidence {check_id!r} exited {artifact.get("exit_code")!r}')
            continue
        if not carried and (artifact.get('fingerprint') != current or artifact.get('source_changed')):
            problems.append(f'command evidence {check_id!r} was recorded against different source')
            continue
        entries.append({
            'command_check_id': check_id,
            'command': artifact.get('command'),
            'exit_code': artifact.get('exit_code'),
            'recorded_fingerprint': artifact.get('fingerprint'),
        })
    if kind == 'artifact' and not any('sha256' in row for row in entries):
        problems.append('artifact evidence names no readable file')
    if kind == 'command' and not any('command_check_id' in row for row in entries):
        problems.append('command evidence names no passing command result')
    evidence = {
        'kind': kind,
        'summary': summary,
        'items': entries,
        'verified': kind in VERIFIABLE_EVIDENCE_KINDS and not problems,
    }
    return evidence, entries, problems


def derive_profile(consequence, surface):
    """Return the only check profile the declared risk allows.

    ``consequence`` asks whether a wrong result hurts the user (missed train,
    lost money, leaked data); ``surface`` asks how far the change reaches.  The
    mapping is deliberately strict: ``full`` is reserved for high-consequence
    changes that also reach wide, so low-risk polish cannot buy a full
    re-verification and high-consequence single facts cannot hide behind smoke.
    """
    if consequence == 'high':
        return 'full' if surface == 'wide' else 'targeted'
    return 'smoke'


def carried_evidence_paths(item):
    raw = item.get('evidence')
    if not isinstance(raw, dict):
        return []
    return [str(value) for key in PATH_KEYS for value in (raw.get(key) or [])]


def normalize_verify_command(raw):
    """Accept a shell-ish command string or argv list; return a list or None."""
    if raw is None:
        return None
    if isinstance(raw, str):
        value = raw.strip()
        return [value] if value else None
    if isinstance(raw, list):
        parts = [str(part) for part in raw if str(part).strip()]
        return parts or None
    raise ValueError('verify_command must be a string or a list of strings')


def validate_carry(root, item, identifier):
    """Validate a ``carried_from`` reference to an earlier matrix item.

    Carrying is the explicit, disclosed form of incremental re-verification.
    The tool proves the link: the prior matrix exists and contains this id as a
    passed item with the same blocking role.  It cannot prove that the change
    since then left the item untouched, so that relevance judgement stays with
    the checker and is disclosed in the matrix and the delivery receipt.
    """
    prior_id = str(item.get('carried_from') or '').strip()
    if not prior_id:
        return None
    prior = load_check_artifact(root, prior_id)
    if prior.get('kind') != 'matrix':
        raise ValueError(f'Matrix item {identifier!r} carried_from {prior_id!r} is not a matrix artifact')
    matches = [row for row in prior.get('items') or [] if row.get('id') == identifier]
    if not matches:
        raise ValueError(f'Matrix item {identifier!r} does not exist in carried_from {prior_id!r}')
    source = matches[0]
    if source.get('status') != 'passed':
        raise ValueError(
            f'Matrix item {identifier!r} carried_from {prior_id!r} was {source.get("status")!r}, not passed'
        )
    if bool(source.get('blocking')) != bool(item.get('blocking')):
        raise ValueError(
            f'Matrix item {identifier!r} changes its blocking role relative to carried_from {prior_id!r}'
        )
    return {
        'check_id': prior_id,
        'fingerprint': prior.get('fingerprint'),
        'matrix_status': prior.get('status'),
        'status': source.get('status'),
        'blocking': bool(source.get('blocking')),
        'limit': 'The tool verified this link only; that the change left this item unaffected is the checker judgement',
    }


def matrix_check(root, payload, label=None, save_evidence=False, profile=None):
    head = payload if isinstance(payload, dict) else {}
    consequence = str(head.get('consequence') or '').strip().lower()
    surface = str(head.get('surface') or '').strip().lower()
    if consequence not in CHECK_CONSEQUENCES:
        raise ValueError(
            f'Check matrix needs "consequence" (one of {CHECK_CONSEQUENCES}): would a wrong result hurt the '
            'user (missed train, lost money, leaked data) or only look wrong'
        )
    if surface not in CHECK_SURFACES:
        raise ValueError(
            f'Check matrix needs "surface" (one of {CHECK_SURFACES}): how far does this round\'s change reach'
        )
    derived = derive_profile(consequence, surface)
    declared = profile or head.get('profile')
    if not declared:
        raise ValueError('Check matrix needs "profile"; it must equal the profile derived from consequence and surface')
    declared = str(declared).strip().lower()
    if declared not in CHECK_PROFILES:
        raise ValueError(f'Check profile must be one of {CHECK_PROFILES}, got {declared!r}')
    if declared != derived:
        raise ValueError(
            f'consequence={consequence!r} + surface={surface!r} allows only profile {derived!r}, got {declared!r}. '
            'Raise the declared risk if the higher profile is truly needed; do not spend a wider check than the risk'
        )
    profile = derived
    profile_reason = str(head.get('profile_reason') or '').strip()
    if not profile_reason:
        raise ValueError('Check matrix needs a non-empty profile_reason explaining why this scope was selected')
    items = payload.get('items') if isinstance(payload, dict) else payload
    if not isinstance(items, list) or not items:
        raise ValueError('Check matrix needs a non-empty list of items')
    before = fingerprint(root)
    seen = set()
    normalized = []
    artifacts: dict[str, dict] = {}
    failures = []
    carried_ids = []
    archived_paths: set[str] = set()
    evidence_dir = root / '.site' / CHECK_ARTIFACT_DIR / 'evidence'
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f'Matrix item {index} must be an object')
        identifier = item.get('id')
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f'Matrix item {index} needs a non-empty string "id"')
        identifier = identifier.strip()
        if identifier in seen:
            raise ValueError(f'Duplicate matrix item id: {identifier!r}')
        seen.add(identifier)
        status = item.get('status')
        if status not in CHECK_STATUSES:
            raise ValueError(f'Matrix item {identifier!r} status must be one of {CHECK_STATUSES}')
        if not isinstance(item.get('blocking'), bool):
            raise ValueError(f'Matrix item {identifier!r} needs a boolean "blocking"')
        axis = item.get('axis')
        if not isinstance(axis, str) or not axis.strip():
            raise ValueError(f'Matrix item {identifier!r} needs a non-empty string "axis"')
        axis = axis.strip()
        carried = validate_carry(root, item, identifier)
        if carried and profile not in CARRY_PROFILES:
            raise ValueError(
                f'Matrix item {identifier!r} uses carried_from under profile {profile!r}. A full check is full: '
                'run every item again instead of carrying earlier results'
            )
        try:
            evidence, entries, problems = validate_evidence(
                root, item, identifier, before, {}, carried=bool(carried)
            )
        except ValueError as error:
            failures.append({'id': identifier, 'reason': f'unverifiable evidence: {error}'})
            evidence, entries, problems = {'kind': 'declared', 'summary': '', 'items': [], 'verified': False}, [], []
        if evidence['kind'] in VERIFIABLE_EVIDENCE_KINDS and status == 'passed' and problems:
            failures.append({'id': identifier, 'reason': '; '.join(problems)})
        if item['blocking'] and status == 'passed' and not evidence['verified']:
            failures.append({
                'id': identifier,
                'reason': 'blocking item is passed without verified evidence',
            })
        paths = carried_evidence_paths(item)
        if len(paths) > EVIDENCE_BUDGET_PER_ITEM:
            raise ValueError(
                f'Matrix item {identifier!r} references {len(paths)} evidence files; the budget is '
                f'{EVIDENCE_BUDGET_PER_ITEM} per item. Keep the ones that changed a verdict and drop the rest'
            )
        archived_paths.update(paths)
        for row in entries:
            if 'sha256' in row:
                artifacts[row['path']] = row
        normalized.append({
            'id': identifier,
            'axis': axis,
            'title': str(item.get('title') or identifier),
            'status': status,
            'blocking': item['blocking'],
            'carried_from': carried,
            'verify_command': normalize_verify_command(item.get('verify_command')),
            'evidence': evidence,
        })
        if carried:
            carried_ids.append({'id': identifier, 'axis': axis, 'check_id': carried['check_id']})
    if len(archived_paths) > EVIDENCE_BUDGET_TOTAL:
        raise ValueError(
            f'This matrix references {len(archived_paths)} evidence files; the budget is {EVIDENCE_BUDGET_TOTAL} '
            'for the whole round. A folder of screenshots is not a conclusion: keep one that changes each verdict'
        )
    required_axes = FULL_REQUIRED_AXES if profile == 'full' else ('core_task',)
    covered_axes = {item['axis'] for item in normalized if item['blocking']}
    missing_axes = [axis for axis in required_axes if axis not in covered_axes]
    if missing_axes:
        raise ValueError(
            f'Profile {profile!r} is missing required blocking axes: {", ".join(missing_axes)}'
        )
    fresh_axes = {
        item['axis'] for item in normalized if item['blocking'] and not item.get('carried_from')
    }
    unfresh_axes = [axis for axis in required_axes if axis not in fresh_axes]
    if unfresh_axes and carried_ids:
        raise ValueError(
            'Every required axis needs at least one item checked again this round; '
            f'carried results alone cover: {", ".join(unfresh_axes)}'
        )
    if save_evidence:
        for row in artifacts.values():
            source = root / row['path']
            if '.site' in Path(row['path']).parts:
                continue
            destination = evidence_dir / Path(row['path']).name
            counter = 2
            while destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != row['sha256']:
                destination = evidence_dir / f'{Path(row["path"]).stem}-{counter}{Path(row["path"]).suffix}'
                counter += 1
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            row['saved_as'] = destination.relative_to(root).as_posix()
    after = fingerprint(root)
    blocking_not_passed = [
        item['id'] for item in normalized if item['blocking'] and item['status'] != 'passed'
    ]
    counts = {status: sum(1 for item in normalized if item['status'] == status) for status in CHECK_STATUSES}
    return {
        'schema_version': 1,
        'kind': 'matrix',
        'created_at': now(),
        'label': label or '',
        'profile': profile,
        'profile_reason': profile_reason,
        'consequence': consequence,
        'surface': surface,
        'derived_profile': derived,
        'input_fingerprint': before,
        'fingerprint': after,
        'source_changed': before != after,
        'items': normalized,
        'artifacts': artifacts,
        'carried_items': carried_ids,
        'fresh_item_count': sum(1 for item in normalized if not item.get('carried_from')),
        'evidence_failures': failures,
        'counts': counts,
        'blocking_not_passed': blocking_not_passed,
        'status': 'failed' if (blocking_not_passed or failures or before != after) else 'passed',
        'limits': [
            'The matrix verifies that declared evidence exists and is unchanged; it does not execute browser, visual or reopening checks by itself',
            'Only artifact and command evidence can carry a blocking item; declared and observation evidence is reported but never proves a pass',
            'Content-addressed artifacts expose accidental edits but are not signed or hostile-writer-proof',
            'A carried item proves only that an earlier round passed it; that this change left it unaffected is the checker judgement, and must be told to the user',
        ],
        'follow_up': [
            'Fix blocking failures in site-builder',
            'Re-check affected items and carry the rest, or run the whole matrix again against a newly frozen fingerprint',
        ],
    }


def reverify_check(root, prior_id, label=None, save_evidence=False, timeout=120):
    """Re-run a passed matrix cheaply: execute its assertions instead of re-deriving them.

    Exploration is expensive and worth it once.  Re-verification should not be,
    because nothing new is being discovered - the same conclusions just have to
    be confirmed against new source.  That is only cheap if the conclusions were
    recorded as *executable* assertions.

    An item carrying ``verify_command`` is re-run for real and counts as freshly
    checked.  An item without one cannot be re-derived automatically, so it is
    carried from the earlier round and disclosed as such.  ``full`` refuses:
    a full check is an exploration, not a replay.
    """
    prior = load_check_artifact(root, prior_id)
    if prior.get('kind') != 'matrix':
        raise ValueError(f'reverify needs a matrix artifact, {prior_id!r} is a {prior.get("kind")!r}')
    if prior.get('status') != 'passed':
        raise ValueError(f'reverify needs a passed matrix; {prior_id!r} is {prior.get("status")!r}')
    profile = prior.get('profile')
    if profile == 'full':
        raise ValueError(
            'A full check is an exploration, not a replay: re-run it as a full matrix instead of reverify. '
            'Reverify is for smoke and targeted rounds where most items are known-good'
        )
    consequence, surface = prior.get('consequence'), prior.get('surface')
    if not consequence or not surface:
        raise ValueError(
            f'prior matrix {prior_id!r} predates the consequence/surface rule, so its profile cannot be re-derived. '
            'Record a new matrix that declares both fields, then reverify that'
        )

    items, rerun, carried = [], [], []
    for row in prior.get('items') or []:
        identifier = row.get('id')
        command = normalize_verify_command(row.get('verify_command'))
        entry = {
            'id': identifier,
            'axis': row.get('axis'),
            'title': row.get('title'),
            'blocking': bool(row.get('blocking')),
        }
        if command:
            entry['verify_command'] = command
            result = finalize(root, run_check(root, command, timeout))
            entry['evidence'] = {
                'kind': 'command',
                'summary': f'复验重跑：{" ".join(command)}',
                'commands': [result['check_id']],
            }
            entry['status'] = 'passed' if result.get('status') == 'passed' else 'failed'
            if entry['status'] == 'failed':
                tail = (result.get('stderr') or result.get('stdout') or '').strip().splitlines()[-3:]
                entry['evidence']['summary'] += '；失败输出：' + ' / '.join(tail)
            rerun.append(identifier)
        else:
            evidence = row.get('evidence') if isinstance(row.get('evidence'), dict) else {}
            paths = [
                str(item.get('saved_as') or item.get('path'))
                for item in (evidence.get('items') or [])
                if isinstance(item, dict) and (item.get('saved_as') or item.get('path'))
            ]
            if evidence.get('kind') in VERIFIABLE_EVIDENCE_KINDS and row.get('status') == 'passed':
                entry['carried_from'] = prior_id
                entry['evidence'] = {
                    'kind': evidence.get('kind'),
                    'summary': f'沿用上一轮结论（{prior_id[:12]}），本轮未重新检查：{evidence.get("summary", "")}'.strip(),
                    'commands': [
                        item.get('command_check_id')
                        for item in (evidence.get('items') or [])
                        if isinstance(item, dict) and item.get('command_check_id')
                    ],
                    'paths': paths,
                }
                entry['status'] = 'passed'
                carried.append(identifier)
            else:
                # Non-passing, non-blocking items (e.g. not_run) cannot be carried;
                # restate them so the new matrix still discloses the same gap.
                entry['status'] = row.get('status')
                entry['evidence'] = {
                    'kind': evidence.get('kind') or DEFAULT_EVIDENCE_KIND,
                    'summary': f'沿用上一轮披露：{evidence.get("summary", "")}'.strip(),
                }
        items.append(entry)

    payload = {
        'consequence': consequence,
        'surface': surface,
        'profile': profile,
        'profile_reason': (
            f'对 {prior_id[:12]} 的增量复验：{len(rerun)} 项重跑可执行断言，'
            f'{len(carried)} 项沿用上一轮结论且已在矩阵中标明。'
            + (prior.get('profile_reason') or '')
        ),
        'items': items,
    }
    output = matrix_check(root, payload, label or f'reverify {prior_id[:12]}', save_evidence)
    output['reverify_of'] = prior_id
    return output


def css_urls(text):
    pattern = r'''url\(\s*(["']?)(.*?)\1\s*\)|@import\s+["']([^"']+)["']'''
    for match in re.finditer(pattern, text, re.I):
        value = match.group(2) if match.group(2) is not None else match.group(3)
        yield value, text.count('\n', 0, match.start())


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = {}
        self.idrefs = []
        self.refs = []
        self.in_style = False

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        line = self.getpos()[0]
        if attrs.get('id'):
            self.ids.setdefault(attrs['id'], []).append(line)
        for key in ('for', 'aria-labelledby', 'aria-describedby', 'aria-controls', 'aria-errormessage', 'list', 'headers'):
            for value in (attrs.get(key) or '').split():
                self.idrefs.append((value, line))
        keys = {'src', 'poster', 'href', 'data'} if tag == 'object' else {'src', 'poster', 'href'}
        for key in keys:
            if key in attrs:
                self.refs.append((attrs[key] or '', tag not in ('a', 'area'), line))
        srcset = attrs.get('srcset') or ''
        if srcset and not srcset.strip().startswith('data:'):
            for entry in srcset.split(','):
                if entry.strip():
                    self.refs.append((entry.strip().split()[0], True, line))
        for value, offset in css_urls(attrs.get('style') or ''):
            self.refs.append((value, True, line + offset))
        self.in_style = tag == 'style' or self.in_style

    def handle_endtag(self, tag):
        if tag == 'style':
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            for value, offset in css_urls(data):
                self.refs.append((value, True, self.getpos()[0] + offset))


def static_check(root, offline=False, web_root=None):
    if web_root:
        requested_web = root / web_root
        if requested_web.is_symlink():
            raise ValueError('Web root must be a regular directory inside the project')
        web = requested_web.resolve()
    else:
        web = root / 'web' if (root / 'web').is_dir() else root
    if not web.is_dir() or not web.is_relative_to(root) or web.is_symlink():
        raise ValueError('Web root must be a regular directory inside the project')
    issues = []
    pages = {}

    def issue(code, path, line, message, level='error'):
        row = {
            'code': code,
            'file': path.relative_to(root).as_posix(),
            'line': line,
            'message': message,
            'level': level,
        }
        if row not in issues:
            issues.append(row)

    for path in files(web):
        if path.suffix.lower() not in ('.html', '.htm', '.css'):
            continue
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeError:
            issue('invalid-encoding', path, 1, 'Expected UTF-8')
            continue
        if path.suffix.lower() in ('.html', '.htm'):
            page = Page()
            page.feed(content)
            pages[path.resolve()] = page
            for value, lines in page.ids.items():
                if len(lines) > 1:
                    issue('duplicate-id', path, lines[1], value)
            for value, line in page.idrefs:
                if value not in page.ids:
                    issue('missing-id-reference', path, line, value)
        else:
            page = Page()
            page.refs = [(value, True, line + 1) for value, line in css_urls(content)]

        for value, asset, line in page.refs:
            value = value.strip()
            if not value or value == '#':
                issue('empty-reference', path, line, 'Use a real destination or a button')
                continue
            parsed = urlsplit(value)
            if parsed.scheme in ('http', 'https') or value.startswith('//'):
                if offline and asset:
                    issue('external-offline-dependency', path, line, value)
                continue
            if parsed.scheme in ('data', 'blob', 'mailto', 'tel'):
                continue
            if parsed.scheme:
                issue('unsupported-url-scheme', path, line, parsed.scheme, 'warning')
                continue
            local = unquote(parsed.path)
            target = (web / local.lstrip('/') if local.startswith('/') else path.parent / local) if local else path
            resolved = target.resolve()
            if not resolved.is_relative_to(web):
                issue('outside-web-root', path, line, value)
            elif target.is_symlink():
                issue('symlink-resource', path, line, value)
            elif target.is_dir() and (target / 'index.html').is_file():
                pass
            elif not target.is_file():
                if not asset and local and not Path(local).suffix:
                    issue('unverified-client-route', path, line, value, 'warning')
                else:
                    issue('missing-local-target', path, line, value)

    for path, page in pages.items():
        for value, asset, line in page.refs:
            parsed = urlsplit(value)
            if asset or parsed.scheme or not parsed.fragment or value.startswith('//'):
                continue
            local = unquote(parsed.path)
            target = (web / local.lstrip('/') if local.startswith('/') else path.parent / local) if local else path
            if target.is_dir():
                target = target / 'index.html'
            other = pages.get(target.resolve())
            if other is not None and unquote(parsed.fragment) not in other.ids:
                issue('missing-fragment', path, line, value)

    if not pages:
        issue('no-html-files', web, 1, 'Run project-native build and browser checks', 'warning')
    errors = sum(item['level'] == 'error' for item in issues)
    return {
        'schema_version': 1,
        'kind': 'static',
        'created_at': now(),
        'fingerprint': fingerprint(root),
        'status': 'failed' if errors else ('not_applicable' if not pages else 'passed'),
        'issues': issues,
        'limits': ['No JavaScript execution, runtime interaction, full CSS parsing, security audit or visual verification'],
        'follow_up': ['Run project-native checks', 'Exercise required user tasks', 'Request site-design visual review', 'Verify reopening and data'],
    }


def run_check(root, command, timeout):
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        raise ValueError('Provide an actual check command after --')
    before = fingerprint(root)
    try:
        result = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout,
            errors='replace',
        )
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        code, stdout, stderr = None, '', 'Check timed out; inspect child processes before retrying'
    after = fingerprint(root)
    return {
        'schema_version': 1,
        'kind': 'command',
        'created_at': now(),
        'command': command,
        'input_fingerprint': before,
        'fingerprint': after,
        'source_changed': before != after,
        'exit_code': code,
        'stdout': stdout[-20000:],
        'stderr': stderr[-20000:],
        'status': 'passed' if code == 0 and before == after else 'failed',
        'limits': ['Command success only; not automatic business, visual or reopening acceptance'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    static = commands.add_parser('static')
    static.add_argument('root', type=Path)
    static.add_argument('--offline', action='store_true')
    static.add_argument('--web-root')
    run = commands.add_parser('run')
    run.add_argument('root', type=Path)
    run.add_argument('--timeout', type=int, default=120)
    run.add_argument('command', nargs=argparse.REMAINDER)
    matrix = commands.add_parser('matrix')
    matrix.add_argument('root', type=Path)
    matrix.add_argument('--input', required=True, help='JSON file with the checked items and their evidence')
    matrix.add_argument('--label')
    matrix.add_argument('--profile', choices=CHECK_PROFILES,
                        help='must equal the profile derived from consequence x surface; a wider profile is refused')
    matrix.add_argument('--save-evidence', action='store_true',
                        help='copy referenced evidence into .site/checks/evidence so re-runs cannot overwrite it')
    reverify = commands.add_parser('reverify', help='re-run a passed matrix by executing its verify_command assertions')
    reverify.add_argument('root', type=Path)
    reverify.add_argument('prior', help='check_id of the passed matrix to re-verify')
    reverify.add_argument('--label')
    reverify.add_argument('--timeout', type=int, default=120, help='per-assertion timeout in seconds')
    reverify.add_argument('--save-evidence', action='store_true')
    args = parser.parse_args()

    try:
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError('Project root must be a directory')
        if args.action == 'static':
            output = static_check(root, args.offline, args.web_root)
        elif args.action == 'run':
            output = run_check(root, args.command, args.timeout)
        elif args.action == 'reverify':
            output = reverify_check(root, args.prior, args.label, args.save_evidence, args.timeout)
        else:
            payload = json.loads(Path(args.input).expanduser().read_text(encoding='utf-8'))
            output = matrix_check(root, payload, args.label, args.save_evidence, args.profile)
        output = finalize(root, output)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1 if output.get('status') == 'failed' else 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
