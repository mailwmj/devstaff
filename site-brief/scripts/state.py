#!/usr/bin/env python3
"""Collaboration state gate for the site skill suite. Python 3.10+, standard library only.

Every ``.site/state.json`` transition after project initialization goes through this
tool.  It replaces "remember the rules" with mechanical checks:

* gate commands refuse a transition whose basis is missing;
* the writer/checker lease makes concurrent Writer and Checker impossible;
* ``handoff`` records stopped PIDs, freed ports and the frozen fingerprint;
* ``start-verify`` refuses unless the source still matches that frozen fingerprint;
* ``deliver`` only accepts a ``site-check`` matrix artifact (``check_id``) whose
  filename, internal id and canonical content digest agree, whose fingerprint
  equals the current project fingerprint and whose blocking items all passed;
* exact confirmation wording and compact before/after state summaries stay in the
  audit history, while normalized quote hashes are used only for duplicate checks.

A page has two separate decisions, and this tool keeps them apart:

* ``confirm-structure`` records which structure the creator picked;
* ``confirm-visual`` records the style they picked on top of that structure.

Picking a structure is not a visual confirmation, so ``confirm-visual`` refuses
to run while the structure decision is still unrecorded, and an already recorded
structure choice invalidates a style choice made for the old one.  The rule fails
closed: ``confirm-concept`` treats an omitted ``--structure-directions`` as
"several structures were compared", and only an explicit ``1`` says this round
showed a single page.  Forgetting the flag therefore blocks the style step
instead of silently turning a structure pick into a style choice.

What this tool can and cannot guarantee
---------------------------------------

Nothing this tool writes can prove that the creator agreed to anything.  The
creator's judgement lives in their head, and every file here is writable by the
agent the gate is supposed to be restraining.  So the four confirmation gates
(``confirm-concept``, ``confirm-structure``, ``confirm-visual``,
``authorize-build``) are **records of what the agent says the creator said**,
not verified facts:

* the caller must pass ``--quote`` with the creator's own words, verbatim;
* an optional ``--anchor`` upgrades the label when the quote can be located in a
  user-role message of a host transcript, and an unreadable host format simply
  downgrades the label instead of failing the gate;
* neither label is forgery-proof, and the record says so in ``basis_note``.

The gate makes accidental drift visible: records are verbatim, timestamped,
revisioned and content-addressed where appropriate. A writer with project access
can still rebuild all local files consistently, so the tool does not, and must not
claim to, keep a hostile agent honest. The verification that matters happens when
the creator is shown their own words again at delivery time.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
from datetime import datetime, timezone

try:
    from state_consent import (
        CONSENT_FIELDS,
        build_consent as _build_consent,
        consent_replay as _consent_replay,
        describe_consent as _describe_consent,
        record_consent as _record_consent,
    )
except ImportError:  # pragma: no cover - supports direct package imports
    from .state_consent import (
        CONSENT_FIELDS,
        build_consent as _build_consent,
        consent_replay as _consent_replay,
        describe_consent as _describe_consent,
        record_consent as _record_consent,
    )

SKIP = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', '.next', '.cache'}
STAGES = (
    'discovering',
    'concept_review',
    'visual_drafting',
    'visual_review',
    'ready_to_build',
    'building',
    'verifying',
    'delivered',
    'blocked',
)
CHECK_STATUSES = ('passed', 'failed', 'not_run', 'not_applicable')
CHECK_ARTIFACT_DIR = 'checks'
CONSENT_FIELDS = ('concept_consent', 'structure_consent', 'visual_consent', 'authorization_consent')

# Consent labels.  Neither is a proof; they are honesty levels, ordered.
BASIS_REPORTED = 'agent-reported'
BASIS_QUOTE_MATCHED = 'quote-matched'
BASIS_NOTE = (
    'Recorded from the caller\'s verbatim quote. Neither label proves the creator '
    'agreed: files are writable by the agent, so this is an auditable record, not a '
    'verified fact. Replay the quote to the creator at delivery time.'
)
ANCHOR_NOTE = (
    'The quote was found in a user-role message of the record the caller pointed at. '
    'It is consistent with a pointer, not a host-issued proof of consent.'
)

# Host transcript shapes are an optional enhancement, never a precondition.  These
# are recognised best-effort so that an unrecognised host degrades the label rather
# than stopping the workflow.
TRANSCRIPT_SUFFIXES = ('.jsonl', '.json', '.ndjson')
ANCHOR_AGENT_ROLES = frozenset({'assistant', 'agent', 'model', 'system', 'tool'})
ANCHOR_USER_ROLES = frozenset({'user', 'human'})


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        temporary = handle.name
    os.replace(temporary, path)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def project_files(root):
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
    """Must stay byte-identical to ``site-check/scripts/check.py``'s implementation."""
    digest = hashlib.sha256()
    paths = list(project_files(root))
    metadata = root / '.site'
    if metadata.is_symlink():
        raise ValueError('Project metadata must not be a symlink')
    design = metadata / 'design'
    if design.exists() and (design.is_symlink() or not design.is_dir()):
        raise ValueError('Project design metadata must be a regular directory')
    if design.is_dir():
        paths.extend(path for path in project_files(design) if path.is_file())
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


def metadata_dir(root):
    folder = root / '.site'
    if folder.is_symlink():
        raise ValueError('Project metadata must not be a symlink')
    return folder


def load_state(root):
    folder = metadata_dir(root)
    path = folder / 'state.json'
    if path.is_symlink():
        raise ValueError('Project state must not be a symlink')
    if not path.is_file():
        raise ValueError('No .site/state.json in this project; initialize it before recording collaboration state')
    try:
        state = read_json(path)
    except json.JSONDecodeError as error:
        raise ValueError(f'Damaged project state; preserve it and inspect project files: {error}') from error
    if not isinstance(state, dict):
        raise ValueError('Damaged project state; preserve it and inspect project files')
    schema = state.get('schema_version')
    if schema == 1:
        state = migrate_v1(state)
    elif schema != 2:
        raise ValueError('Unsupported project state; preserve it and inspect project files')
    if not isinstance(state.get('project_id'), str) or not state['project_id']:
        raise ValueError('Damaged project state; preserve it and inspect project files')
    return state


def migrate_v1(state):
    upgraded = dict(state)
    upgraded['schema_version'] = 2
    legacy = state.get('stage') or state.get('status')
    # Old free-form statuses such as "ready" are not v2 stages and never imply a gate.
    upgraded['stage'] = legacy if legacy in STAGES else 'concept_review'
    upgraded.setdefault('visual_required', True)
    for field in (
        'concept_confirmed',
        'structure_required',
        'structure_confirmed',
        'visual_confirmed',
        'development_authorized',
        'delegated',
    ):
        upgraded.setdefault(field, False)
    upgraded.setdefault('runtime', None)
    return upgraded


def state_summary(state):
    release = state.get('writer_release') if isinstance(state.get('writer_release'), dict) else {}
    delivery = state.get('delivery') if isinstance(state.get('delivery'), dict) else {}
    return {
        'stage': state.get('stage') or state.get('status'),
        'revision': state.get('revision'),
        'concept_confirmed': bool(state.get('concept_confirmed')),
        'structure_required': bool(state.get('structure_required')),
        'structure_confirmed': bool(state.get('structure_confirmed')),
        'visual_confirmed': bool(state.get('visual_confirmed')),
        'development_authorized': bool(state.get('development_authorized')),
        'writer_release_fingerprint': release.get('fingerprint'),
        'delivery_check_id': delivery.get('check_id'),
    }


def save_state(root, state, action, expect_revision=None):
    if expect_revision is not None and state.get('revision') != expect_revision:
        raise ValueError(
            f"Revision conflict: expected {expect_revision}, file has {state.get('revision')}; re-read the project"
        )
    state_path = root / '.site' / 'state.json'
    before_state = read_json(state_path)
    if before_state.get('schema_version') == 1:
        before_state = migrate_v1(before_state)
    before = state_summary(before_state)
    state['schema_version'] = 2
    if 'status' in state:
        state['status'] = state['stage']
    state['revision'] = int(state.get('revision') or 0) + 1
    recorded_at = now()
    state['updated_at'] = recorded_at
    state['last_action'] = action
    lease = read_lease(root)
    transition = {
        'at': recorded_at,
        'action': action,
        'actor': lease.get('owner') if lease else None,
        'lease_role': lease.get('role') if lease else None,
        'before': before,
        'after': state_summary(state),
    }
    state['transition_history'] = as_list(state.get('transition_history')) + [transition]
    write_json(state_path, state)
    return state


def as_list(value):
    return value if isinstance(value, list) else []


def lease_path(root):
    return metadata_dir(root) / 'lease.json'


def read_lease(root):
    path = lease_path(root)
    if path.is_symlink():
        raise ValueError('Project lease must not be a symlink')
    if not path.is_file():
        return None
    try:
        lease = read_json(path)
    except json.JSONDecodeError as error:
        raise ValueError(f'Damaged lease file; preserve it and inspect: {error}') from error
    return lease if isinstance(lease, dict) else None


def require_lease(root, role):
    lease = read_lease(root)
    if not lease:
        raise ValueError(f'No active lease; run claim before acting as {role}')
    if lease.get('role') != role:
        raise ValueError(f"Lease is held by {lease.get('role')!r}; a {role} cannot run concurrently")
    return lease


def write_lease(root, role, owner):
    lease = {'role': role, 'owner': owner, 'acquired_at': now()}
    write_json(lease_path(root), lease)
    return lease


def clear_lease(root):
    path = lease_path(root)
    if path.is_file() and not path.is_symlink():
        path.unlink()


def pid_is_running(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            return False
    return True


def check_artifacts(root):
    folder = metadata_dir(root) / CHECK_ARTIFACT_DIR
    if not folder.is_dir() or folder.is_symlink():
        return []
    rows = []
    for path in sorted(folder.glob('*.json')):
        if path.is_symlink():
            continue
        try:
            data = read_json(path)
            validate_artifact_identity(data, path.stem, path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            rows.append({'check_id': path.stem, 'artifact': str(path), 'error': str(error)})
            continue
        rows.append({
            'check_id': data.get('check_id', path.stem),
            'kind': data.get('kind'),
            'status': data.get('status'),
            'fingerprint': data.get('fingerprint'),
            'created_at': data.get('created_at'),
            'artifact': path.relative_to(root).as_posix(),
        })
    return rows


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
    if not isinstance(artifact, dict):
        raise ValueError(f'Damaged check artifact {check_id!r}')
    if artifact.get('check_id') != check_id or path.stem != check_id:
        raise ValueError(f'Damaged check artifact {check_id!r}: filename and internal check_id differ')
    if artifact_digest(artifact) != check_id:
        raise ValueError(f'Damaged check artifact {check_id!r}: content digest does not match check_id')
    expected = f'.site/{CHECK_ARTIFACT_DIR}/{check_id}.json'
    if artifact.get('artifact') != expected:
        raise ValueError(f'Damaged check artifact {check_id!r}: artifact path does not match its filename')


def load_artifact(root, check_id):
    if not check_id or any(part in check_id for part in ('/', '\\', '..')):
        raise ValueError('check_id must be a plain identifier')
    path = metadata_dir(root) / CHECK_ARTIFACT_DIR / f'{check_id}.json'
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'No check artifact for check_id {check_id!r} under .site/checks/')
    try:
        artifact = read_json(path)
    except json.JSONDecodeError as error:
        raise ValueError(f'Damaged check artifact {check_id!r}: {error}') from error
    if not isinstance(artifact, dict):
        raise ValueError(f'Damaged check artifact {check_id!r}')
    validate_artifact_identity(artifact, check_id, path)
    return artifact


def regular_file(root, raw, option):
    path = Path(raw).expanduser()
    if path.is_symlink():
        raise ValueError(f'{option} must not be a symlink: {raw}')
    if not path.is_file():
        raise ValueError(f'{option} must be a regular file: {raw}')
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f'{option} must be a regular file inside the project: {raw}')
    parent = path.absolute().parent
    while parent != parent.parent:
        if parent.is_symlink():
            raise ValueError(f'{option} parent directory must not be a symlink: {raw}')
        if parent.resolve() == root:
            break
        parent = parent.parent
    return resolved


def validate_surface_brief(root, raw):
    """Require the minimum auditable design record for a visual decision.

    The gate checks that the direction was documented, not whether the direction
    is good. Semantic quality and the relevance of rejected candidates remain a
    human/Checker judgement.
    """
    resolved = regular_file(root, raw, '--surface-brief')
    text = resolved.read_text(encoding='utf-8')
    if not re.search(r'ui-ux-pro-max', text, re.IGNORECASE):
        raise ValueError(
            '--surface-brief must record the bundled ui-ux-pro-max source before visual confirmation'
        )
    has_query = bool(re.search(r'(?:query|查询)\s*[:：]\s*[^|\n]+\S', text, re.IGNORECASE))
    has_style_id = bool(re.search(
        r'(?:style[_ -]?id|result[_ -]?id)\s*[:：]\s*[`"\']?([A-Za-z0-9][A-Za-z0-9._-]*)',
        text,
        re.IGNORECASE,
    ))
    explicit_no_match = bool(re.search(r'\bno_verified_match\b', text, re.IGNORECASE))
    if not has_query or not (has_style_id or explicit_no_match):
        raise ValueError(
            '--surface-brief must include a recorded design.py query and a non-empty Style/Result ID; '
            'use no_verified_match only when the query was executed but produced no verified result'
        )
    evidence_patterns = {
        'category default': r'(?:类别默认|默认答案|category\s+default)',
        'anti-default reason': r'(?:反默认原因|反默认理由|anti[- ]default(?:\s+reason)?)',
        'replacement': r'(?:替代结构|替代答案|replacement)',
        'swap check': r'(?:交换检查结论|交换检查|swap\s+check)',
        'structural difference evidence': r'(?:结构差异证据|结构差异|structural\s+difference)',
    }
    missing = []
    for name, label in evidence_patterns.items():
        match = re.search(
            rf'(?im)^\s*[-*]\s*(?:\*\*)?{label}\s*[:：]?(?:\*\*)?\s*[:：]?\s*(\S.*)$',
            text,
        )
        if not match or match.group(1).strip().lower() in {'pending', 'todo', '待补', '待填写'}:
            missing.append(name)
    if missing:
        raise ValueError(
            '--surface-brief is missing non-empty direction evidence: ' + ', '.join(missing) +
            '. Record the project default, replacement, candidate difference and swap check; '
            'write not-applicable with a reason when a field does not apply'
        )
    return resolved


def require_visual_contract(root, state=None):
    """Resolve the project contract for visual scopes and fail closed if absent."""
    recorded = state.get('surface_brief') if isinstance(state, dict) else None
    path = Path(recorded) if recorded else root / '.site' / 'design' / 'surface-brief.md'
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        raise ValueError(
            'A visual scope needs .site/design/surface-brief.md before visual confirmation or development'
        )
    return validate_surface_brief(root, str(path))


def gate_reasons(state, visual_required):
    reasons = []
    if not state.get('concept_confirmed'):
        reasons.append('concept_confirmed is false')
    if state.get('structure_required') and not state.get('structure_confirmed'):
        reasons.append('structure_confirmed is false')
    if visual_required and not state.get('visual_confirmed'):
        reasons.append('visual_confirmed is false')
    if not state.get('development_authorized'):
        reasons.append('development_authorized is false')
    return reasons


def parse_services(raw_items):
    services = []
    for raw in raw_items or []:
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(f'--service-json is not valid JSON: {error}') from error
        if not isinstance(item, dict):
            raise ValueError('--service-json must be a JSON object')
        unknown = set(item) - {'owner', 'pid', 'port', 'root'}
        if unknown:
            raise ValueError(f'--service-json has unsupported keys: {sorted(unknown)}')
        owner = item.get('owner')
        port = item.get('port')
        root_text = item.get('root')
        if not isinstance(owner, str) or not owner:
            raise ValueError('--service-json needs a non-empty "owner"')
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError('--service-json needs an integer "port" in 1..65535')
        if not isinstance(root_text, str) or not root_text:
            raise ValueError('--service-json needs a "root" directory')
        root = Path(root_text).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f'service root is not a directory: {root_text}')
        pid = item.get('pid')
        if not isinstance(pid, int) or pid <= 0:
            raise ValueError('--service-json needs a positive integer "pid"')
        services.append({'owner': owner, 'port': port, 'root': str(root), 'pid': pid})
    return services


def action_show(root, args):
    state = load_state(root)
    lease = read_lease(root)
    current = fingerprint(root)
    release = state.get('writer_release') or {}
    return {
        'action': 'show',
        'root': str(root),
        'state': state,
        'stage': state.get('stage'),
        'revision': state.get('revision'),
        'fingerprint': current,
        'lease': lease,
        'writer_release': release or None,
        'release_matches_current_source': bool(release) and release.get('fingerprint') == current,
        'delivery': state.get('delivery'),
        # Two separate decisions, surfaced separately: a recorded structure choice
        # must never read as a visual confirmation just because the page has one
        # direction flag.
        'structure': {
            'required': bool(state.get('structure_required')),
            'confirmed': bool(state.get('structure_confirmed')),
            'prototype': state.get('structure_prototype'),
            'quote': state.get('structure_basis'),
        },
        'visual': {
            'required': bool(state.get('visual_required', True)),
            'confirmed': bool(state.get('visual_confirmed')),
            'prototype': state.get('visual_prototype'),
            'quote': state.get('visual_basis'),
        },
        'consents': {
            field: (
                dict(state[field], quote=state[field].get('quote', '')[:200])
                if isinstance(state.get(field), dict) else None
            )
            for field in CONSENT_FIELDS
        },
        'consent_replay': _consent_replay(state),
        'checks': [
            dict(row, matches_current_source=row.get('fingerprint') == current)
            for row in check_artifacts(root)
        ],
    }


def action_claim(root, args):
    state = load_state(root)
    existing = read_lease(root)
    if args.force and not args.reason:
        raise ValueError('--force requires --reason so the bypass stays auditable')
    if existing and existing.get('role') == 'checker' and state.get('stage') == 'verifying':
        raise ValueError(
            'An active verification lease cannot be force-claimed; '
            'run the Checker matrix, then use reopen --check <failed_check_id>'
        )
    if (
        existing
        and existing.get('role') == 'writer'
        and existing.get('owner') == args.owner
        and not args.force
    ):
        return {
            'action': 'claim',
            'root': str(root),
            'lease': existing,
            'forced': False,
            'idempotent': True,
        }
    if existing and (
        existing.get('role') != 'writer' or existing.get('owner') != args.owner
    ) and not args.force:
        raise ValueError(
            f"Lease is held by {existing.get('role')!r} owner {existing.get('owner')!r} "
            f"since {existing.get('acquired_at')}; "
            'finish or release it, or pass --force with --reason'
        )
    if state.get('stage') == 'delivered' and not args.force:
        raise ValueError('Project is delivered; run reopen before claiming the writer lease again')
    lease = write_lease(root, 'writer', args.owner)
    if args.force:
        state['lease_overrides'] = as_list(state.get('lease_overrides')) + [
            {'at': now(), 'reason': args.reason, 'previous': existing}
        ]
        save_state(root, state, 'claim')
    return {
        'action': 'claim',
        'root': str(root),
        'lease': lease,
        'forced': bool(args.force),
        'idempotent': False,
    }


def action_release(root, args):
    existing = read_lease(root)
    if not existing:
        raise ValueError('No active lease to release')
    if existing.get('owner') != args.owner:
        raise ValueError(
            f"Lease is owned by {existing.get('owner')!r}, not {args.owner!r}; "
            'only the active owner may release it'
        )
    state = load_state(root)
    if existing.get('role') == 'checker' and state.get('stage') == 'verifying':
        raise ValueError(
            'An active verification lease cannot be released; '
            'run the Checker matrix, then use reopen --check <failed_check_id>'
        )
    if args.role and existing.get('role') != args.role:
        raise ValueError(f"Lease role is {existing.get('role')!r}, not {args.role!r}")
    clear_lease(root)
    return {'action': 'release', 'root': str(root), 'released': existing}


def action_confirm_concept(root, args):
    state = load_state(root)
    if state.get('stage') in ('building', 'verifying', 'delivered', 'blocked'):
        raise ValueError(
            f"confirm-concept cannot run at stage {state.get('stage')!r}; unblock, or run reopen --scope-changed, "
            'so the running build, check or delivery is voided first. Re-recording the concept after delivery would '
            'leave a frozen delivery replay quoting a decision that has since been rewritten'
        )
    consent = _build_consent(args)
    visual_required = not args.no_visual
    if args.structure_directions is not None and args.structure_directions < 1:
        raise ValueError('--structure-directions counts the structures shown; it must be 1 or more')
    if not visual_required and (args.structure_directions or 0) >= 2:
        raise ValueError(
            'This round declared no separate visual proposal (--no-visual) and also declared several structures '
            'to compare; a structure choice only exists when there is a visual step, so drop one of the two'
        )
    # Fail closed.  Omitting the count means "assume the creator compared several
    # structures", so the structure decision must be recorded before any style
    # choice; a round that really showed one page says so with ``1``.  Otherwise a
    # forgotten flag would silently turn a structure pick into a style choice,
    # which is the exact defect this gate exists to stop.
    if not visual_required:
        structure_required = False
    elif args.structure_directions is None:
        structure_required = True
    else:
        structure_required = args.structure_directions >= 2
    if args.scope_changed:
        state['structure_confirmed'] = False
        state['visual_confirmed'] = False
        state['development_authorized'] = False
        state['delegated'] = False
        state.pop('delivery', None)
    _record_consent(state, 'concept_consent', consent, 'concept')
    state['concept_confirmed'] = True
    state['visual_required'] = visual_required
    state['structure_required'] = structure_required
    # Keep the recorded decisions consistent with the scope just confirmed. A structure
    # choice only exists in a multi-structure round, and a scope that needs no visual
    # proposal has no design decision at all; leaving one standing would let the replay
    # hand the creator a sentence for a decision the project says does not exist.
    voided = []
    if not visual_required:
        voided = [
            name for name, flag in (('structure', 'structure_confirmed'), ('visual', 'visual_confirmed'))
            if state.get(flag)
        ]
        state['structure_confirmed'] = False
        state['visual_confirmed'] = False
    elif not structure_required and state.get('structure_confirmed'):
        voided = ['structure']
        state['structure_confirmed'] = False
    if voided:
        state['development_authorized'] = False
        state['delegated'] = False
        state.pop('delivery', None)
    state['concept_basis'] = consent['quote'][:200]
    state['concept_confirmed_at'] = now()
    # A scope change voids the downstream choices, so the stage returns to drafting
    # even when the previous round had already reached a later stage.
    if args.scope_changed or state.get('stage') in ('discovering', 'concept_review', None):
        state['stage'] = 'visual_drafting' if visual_required else 'concept_review'
    if not visual_required:
        state['next_action'] = 'Obtain explicit development authorization'
    elif structure_required:
        state['next_action'] = 'Show 2-3 structure directions, then record the chosen structure'
    else:
        state['next_action'] = 'Produce and review a visual prototype'
    save_state(root, state, 'confirm-concept', args.expect_revision)
    return {
        'action': 'confirm-concept',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'concept_confirmed': True,
        'visual_required': visual_required,
        'structure_required': structure_required,
        'voided_decisions': voided,
        'consent': _describe_consent(consent),
    }


def action_confirm_structure(root, args):
    """Record the chosen page structure — a different decision from the style.

    Two things make the old failure impossible rather than merely discouraged: the
    style gate refuses while a declared structure choice is unrecorded, and a
    structure quote cannot be replayed as the style quote because consent records
    are compared by content across gates.  Choosing a structure after a style was
    already chosen also invalidates that style choice, since it was made for a page
    that no longer exists.
    """
    state = load_state(root)
    if not state.get('concept_confirmed'):
        raise ValueError('concept_confirmed is false; confirm the first version before recording a structure choice')
    if not state.get('visual_required', True):
        raise ValueError(
            'This scope needs no separate visual proposal (--no-visual), so there is no structure choice to record'
        )
    # Past authorization the documented path is reopen, not a quiet structure swap:
    # the old authorization, check and delivery must be voided first.
    if state.get('stage') in ('ready_to_build', 'building', 'verifying', 'delivered', 'blocked'):
        raise ValueError(
            f"The page structure cannot be re-decided at stage {state.get('stage')!r}; run reopen "
            '--scope-changed (a plain reopen returns to building and still refuses) so the old authorization, '
            'check and delivery are voided. A blocked project records the blockage, not new decisions'
        )
    consent = _build_consent(args)
    resolved = regular_file(root, args.prototype, '--prototype')
    inside = resolved.is_relative_to(root)
    stale_visual = bool(state.get('visual_confirmed'))
    _record_consent(state, 'structure_consent', consent, 'structure')
    state['structure_required'] = True
    state['structure_confirmed'] = True
    state['structure_basis'] = consent['quote'][:200]
    state['structure_confirmed_at'] = now()
    state['structure_prototype'] = str(resolved)
    if stale_visual:
        state['visual_confirmed'] = False
        state['development_authorized'] = False
        state['delegated'] = False
        state.pop('delivery', None)
    if state.get('stage') in ('discovering', 'concept_review', 'visual_drafting', 'visual_review', None):
        state['stage'] = 'visual_drafting'
    state['next_action'] = (
        'Offer 2-3 complete style options on this same structure and the same real content, then record the style choice'
    )
    save_state(root, state, 'confirm-structure', args.expect_revision)
    return {
        'action': 'confirm-structure',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'structure_confirmed': True,
        'visual_confirmed': bool(state.get('visual_confirmed')),
        'invalidated_stale_visual_choice': stale_visual,
        'next_action': state['next_action'],
        'prototype': str(resolved),
        'prototype_inside_project': inside,
        'consent': _describe_consent(consent),
    }


def action_confirm_visual(root, args):
    state = load_state(root)
    if not state.get('concept_confirmed'):
        raise ValueError('concept_confirmed is false; confirm the first version before recording a visual choice')
    if state.get('visual_required') is False:
        raise ValueError(
            'This scope declared --no-visual; there is no visual choice to record'
        )
    if state.get('structure_required') and not state.get('structure_confirmed'):
        raise ValueError(
            'A structure choice is still pending: the creator compared page structures, not styles, and that is '
            'not a visual confirmation. Record their structure choice with confirm-structure first, then offer '
            '2-3 complete style options on that same structure and record the style choice here'
        )
    if state.get('stage') in ('ready_to_build', 'building', 'verifying', 'delivered', 'blocked'):
        raise ValueError(
            f"The visual style cannot be re-decided at stage {state.get('stage')!r}; run reopen --scope-changed "
            '(a plain reopen returns to building and still refuses) so the old authorization, check and delivery '
            'are voided. A blocked project records the blockage, not new decisions'
        )
    consent = _build_consent(args)
    resolved = regular_file(root, args.prototype, '--prototype')
    inside = resolved.is_relative_to(root)
    contract = None
    contract_arg = getattr(args, 'surface_brief', None)
    if contract_arg:
        contract = validate_surface_brief(root, contract_arg)
    else:
        contract = require_visual_contract(root)
    stale_authorization = bool(state.get('development_authorized'))
    _record_consent(state, 'visual_consent', consent, 'visual')
    state['visual_confirmed'] = True
    state['visual_basis'] = consent['quote'][:200]
    state['visual_confirmed_at'] = now()
    state['visual_prototype'] = str(resolved)
    state['surface_brief'] = str(contract)
    if stale_authorization:
        # The authorization was given for the previous style; it does not carry over.
        state['development_authorized'] = False
        state['delegated'] = False
        state.pop('delivery', None)
    if state.get('stage') in ('discovering', 'concept_review', 'visual_drafting', 'visual_review', None):
        state['stage'] = 'visual_review'
    state['next_action'] = (
        'Re-obtain explicit development authorization for the new style'
        if stale_authorization else 'Obtain explicit development authorization or record a requested change'
    )
    save_state(root, state, 'confirm-visual', args.expect_revision)
    return {
        'action': 'confirm-visual',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'visual_confirmed': True,
        'invalidated_stale_authorization': stale_authorization,
        'prototype': str(resolved),
        'prototype_inside_project': inside,
        'surface_brief': str(contract) if contract else None,
        'surface_brief_validated': bool(contract),
        'consent': _describe_consent(consent),
    }


def action_authorize_build(root, args):
    state = load_state(root)
    if state.get('stage') in ('building', 'verifying', 'delivered', 'blocked'):
        raise ValueError(
            f"authorize-build cannot run at stage {state.get('stage')!r}; unblock, or run reopen --scope-changed, "
            'so the running build, check or delivery is voided before new authorization'
        )
    if not state.get('concept_confirmed'):
        raise ValueError('concept_confirmed is false; a visual choice alone never authorizes development')
    if state.get('structure_required') and not state.get('structure_confirmed'):
        raise ValueError('structure_confirmed is false; record the creator\'s structure choice before development')
    if state.get('visual_required') is not False and not state.get('visual_confirmed'):
        raise ValueError('visual_confirmed is false; show the prototype and get a choice before development')
    if state.get('visual_required') is not False:
        require_visual_contract(root, state)
    consent = _build_consent(args)
    _record_consent(state, 'authorization_consent', consent, 'authorization')
    state['development_authorized'] = True
    state['authorization_basis'] = consent['quote'][:200]
    state['authorized_at'] = now()
    if args.delegated:
        state['delegated'] = True
    state['stage'] = 'ready_to_build'
    state['next_action'] = 'Claim the writer lease and start building the current scope'
    save_state(root, state, 'authorize-build', args.expect_revision)
    return {
        'action': 'authorize-build',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'development_authorized': True,
        'delegated': bool(state.get('delegated')),
        'consent': _describe_consent(consent),
    }


def action_start_build(root, args):
    state = load_state(root)
    lease = require_lease(root, 'writer')
    reasons = gate_reasons(state, state.get('visual_required') is not False)
    if reasons:
        raise ValueError('Gate not satisfied: ' + '; '.join(reasons))
    if state.get('visual_required') is not False:
        require_visual_contract(root, state)
    if state.get('stage') == 'delivered':
        raise ValueError('Project is delivered; run reopen before building again')
    state['stage'] = 'building'
    state['writer_release'] = None
    state['next_action'] = 'Implement the confirmed slices, then hand off to the checker'
    save_state(root, state, 'start-build', args.expect_revision)
    return {
        'action': 'start-build',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'lease_owner': lease.get('owner'),
    }


def action_handoff(root, args):
    state = load_state(root)
    require_lease(root, 'writer')
    if state.get('stage') != 'building':
        raise ValueError(f"handoff requires stage 'building', current stage is {state.get('stage')!r}")
    alive = [pid for pid in args.stopped_pid if pid_is_running(pid)]
    if alive:
        raise ValueError(f'Writer children still running: {alive}; stop them before handing off')
    services = parse_services(args.service_json)
    stopped_services = [item['pid'] for item in services if not pid_is_running(item['pid'])]
    if stopped_services:
        raise ValueError(f'Registered service PIDs are not running: {stopped_services}')
    silent_services = [item['port'] for item in services if port_is_free(item['port'])]
    if silent_services:
        raise ValueError(f'Registered service ports are not listening: {silent_services}')
    service_ports = {item['port'] for item in services}
    occupied = [port for port in args.freed_port if port not in service_ports and not port_is_free(port)]
    if occupied:
        raise ValueError(
            f'Ports still occupied by an unregistered service: {occupied}; stop them or register them with --service-json'
        )
    outside = [item['root'] for item in services if not Path(item['root']).is_relative_to(root)]
    if outside:
        raise ValueError(f'Registered service roots must live inside the project: {outside}')
    state['writer_release'] = {
        'at': now(),
        'fingerprint': fingerprint(root),
        'stopped_pids': list(args.stopped_pid),
        'freed_ports': list(args.freed_port),
        'services': services,
        'note': args.note or '',
    }
    state['next_action'] = 'Run start-verify, then dispatch the independent checker against the registered entry'
    save_state(root, state, 'handoff', args.expect_revision)
    return {
        'action': 'handoff',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'writer_release': state['writer_release'],
    }


def action_start_verify(root, args):
    state = load_state(root)
    lease = require_lease(root, 'writer')
    if state.get('stage') != 'building':
        raise ValueError(f"start-verify requires stage 'building', current stage is {state.get('stage')!r}")
    release = state.get('writer_release')
    if not release:
        raise ValueError('No handoff record; stop the writer services and run handoff before verifying')
    current = fingerprint(root)
    if release.get('fingerprint') != current:
        raise ValueError(
            'Source changed after handoff; the freeze is void. Stop writing and run handoff again before verifying'
        )
    release['consumed_at'] = now()
    write_lease(root, 'checker', lease.get('owner'))
    state['stage'] = 'verifying'
    state['next_action'] = 'Run the independent check matrix and deliver only through its check_id'
    save_state(root, state, 'start-verify', args.expect_revision)
    return {
        'action': 'start-verify',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'frozen_fingerprint': current,
        'lease_role': 'checker',
    }


def verify_delivery_evidence(root, artifact):
    """Re-hash the checker's evidence now, so delivery cannot rest on edited proof.

    Every recorded file is checked twice over: the top-level artifact map and the
    per-item ``evidence.items`` rows.  A matrix whose evidence rows were stripped
    or rewritten therefore fails instead of passing on an empty map.
    """
    problems = []
    recorded = {}

    def collect(rows, where):
        for row in as_list(rows):
            if not isinstance(row, dict):
                problems.append(f'{where}: malformed artifact record')
                continue
            # An archived copy is the evidence of record.  Without one, the work
            # file itself is checked; re-running the checker may legitimately
            # overwrite a work file but never an archived copy.
            archived = row.get('saved_as')
            relative = str(archived or row.get('path') or '')
            if not relative:
                continue
            recorded.setdefault(relative, set()).add(str(row.get('sha256') or ''))

    collect((artifact.get('artifacts') or {}).values(), 'artifact map')
    blocking_artifacts = 0
    for item in as_list(artifact.get('items')):
        if not isinstance(item, dict):
            continue
        evidence = item.get('evidence')
        if not isinstance(evidence, dict):
            continue
        identifier = str(item.get('id'))
        if evidence.get('kind') == 'artifact':
            blocking_artifacts += len(as_list(evidence.get('items')))
        collect(evidence.get('items'), f'item {identifier}')
        if evidence.get('kind') == 'command':
            for entry in as_list(evidence.get('items')):
                check_id = entry.get('command_check_id') if isinstance(entry, dict) else None
                if not check_id:
                    continue
                try:
                    command = load_artifact(root, check_id)
                except ValueError as error:
                    problems.append(f'command evidence {check_id}: {error}')
                    continue
                if command.get('kind') != 'command' or command.get('status') != 'passed':
                    problems.append(f'command evidence {check_id}: stored result is not a passing command')
                elif command.get('fingerprint') != artifact.get('fingerprint') or command.get('source_changed'):
                    problems.append(f'command evidence {check_id}: stored result belongs to different source')
    if blocking_artifacts == 0 and any(
        isinstance(item, dict) and (item.get('evidence') or {}).get('kind') == 'artifact'
        for item in as_list(artifact.get('items'))
    ):
        problems.append('artifact evidence rows are missing; the matrix cannot be re-verified')
    for relative, digests in sorted(recorded.items()):
        path = root / relative
        if path.is_symlink() or not path.is_file():
            problems.append(f'{relative}: evidence file is missing')
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            problems.append(f'{relative}: evidence cannot be read ({error})')
            continue
        if not any(digest == value for value in digests if value):
            problems.append(f'{relative}: evidence changed after the check')
    return problems


def action_deliver(root, args):
    state = load_state(root)
    require_lease(root, 'checker')
    if state.get('stage') != 'verifying':
        raise ValueError(f"deliver requires stage 'verifying', current stage is {state.get('stage')!r}")
    reasons = gate_reasons(state, state.get('visual_required') is not False)
    if reasons:
        raise ValueError(
            'The consent gates are not satisfied, so a stage record alone cannot deliver: ' + '; '.join(reasons) +
            '. If the project lost its confirmations, reopen instead of delivering without them'
        )
    artifact = load_artifact(root, args.check)
    if artifact.get('kind') != 'matrix':
        raise ValueError('deliver needs a site-check matrix artifact, not a single static or command check')
    current = fingerprint(root)
    if artifact.get('fingerprint') != current:
        raise ValueError(
            'Source changed after the check; the acceptance result is void. Fix nothing further and re-run the check'
        )
    if artifact.get('status') != 'passed':
        raise ValueError(f"Check matrix status is {artifact.get('status')!r}; keep verifying and fix the failed items")
    blocking = [item for item in as_list(artifact.get('items')) if item.get('blocking') and item.get('status') != 'passed']
    if blocking:
        raise ValueError(
            'Blocking items are not passed: ' + ', '.join(str(item.get('id')) for item in blocking)
        )
    failures = as_list(artifact.get('evidence_failures'))
    if failures:
        raise ValueError(
            'The check matrix carries unverified blocking evidence: '
            + '; '.join(f"{item.get('id')}: {item.get('reason')}" for item in failures)
        )
    unverified = []
    for item in as_list(artifact.get('items')):
        if not isinstance(item, dict) or not item.get('blocking'):
            continue
        evidence = item.get('evidence')
        if not isinstance(evidence, dict) or evidence.get('kind') not in ('artifact', 'command'):
            unverified.append(f"{item.get('id')} (no verified artifact or command evidence)")
        elif evidence.get('verified') is not True:
            unverified.append(f"{item.get('id')} ({evidence.get('kind')} evidence is not verified)")
    if unverified:
        raise ValueError(
            'Blocking items lack verified evidence: ' + '; '.join(unverified) +
            '. Rewrite the matrix through check.py; a hand-written matrix is not acceptance evidence'
        )
    tampered = verify_delivery_evidence(root, artifact)
    if tampered:
        raise ValueError('Acceptance evidence no longer holds: ' + '; '.join(tampered))
    state['stage'] = 'delivered'
    state['delivery'] = {
        'at': now(),
        'check_id': args.check,
        'fingerprint': current,
        'item_count': len(as_list(artifact.get('items'))),
        'artifact': f'.site/{CHECK_ARTIFACT_DIR}/{args.check}.json',
    }
    state['next_action'] = 'Deliver in plain language; reopen before any further scope change'
    replay = _consent_replay(state)
    state['delivery']['consent_replay'] = [entry['quote'] for entry in replay]
    save_state(root, state, 'deliver', args.expect_revision)
    clear_lease(root)
    return {
        'action': 'deliver',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'delivery': state['delivery'],
        # Show the creator their own words again at the cheapest possible moment to
        # catch a wrong or stale approval. The gate cannot verify consent; the person
        # can, and this is where they are asked to.
        'consent_replay': replay,
        'consent_replay_instruction': (
            'Quote each line back to the creator verbatim and ask them to correct it. '
            'Any line they disown must be reopened before the delivery stands.'
        ),
    }


def action_reopen(root, args):
    state = load_state(root)
    lease = read_lease(root)
    if not args.reason.strip():
        raise ValueError('--reason must record why the delivered or verified state is void')
    failed_check = None
    if state.get('stage') == 'verifying' or (lease and lease.get('role') == 'checker'):
        if not args.check:
            raise ValueError(
                'Reopening an active Checker needs --check with the failed check_id; '
                'run and record the Checker matrix before returning the lease to a Writer'
            )
        failed_check = load_artifact(root, args.check)
        if failed_check.get('kind') != 'matrix' or failed_check.get('status') != 'failed':
            raise ValueError('--check must identify a failed check matrix before the Writer can resume')
        if failed_check.get('fingerprint') != fingerprint(root):
            raise ValueError('The failed check belongs to different source; run the Checker matrix again')
    # reopen hands out a writer lease and a building stage. Without a precondition it
    # is a bypass: a brand-new project could reopen, hand off, verify and deliver with
    # nothing ever confirmed. There must be something to void.
    confirmed = [
        name for name in
        ('concept_confirmed', 'structure_confirmed', 'visual_confirmed', 'development_authorized')
        if state.get(name)
    ]
    if not confirmed and state.get('stage') not in ('building', 'verifying', 'delivered', 'blocked'):
        raise ValueError(
            'Nothing to reopen: this project has no recorded confirmation, verification or delivery yet. '
            'Record progress with confirm-concept/confirm-structure/confirm-visual instead'
        )
    previous = state.get('stage')
    state['stage'] = 'building'
    state.pop('delivery', None)
    state['writer_release'] = None
    if args.scope_changed:
        # The core scope changed, so the first-version concept itself no longer
        # stands: re-confirm it before any downstream decision is recorded again.
        state['concept_confirmed'] = False
        state['structure_confirmed'] = False
        state['visual_confirmed'] = False
        state['development_authorized'] = False
        state['delegated'] = False
        state['stage'] = 'visual_drafting' if state.get('visual_required', True) else 'concept_review'
    state['reopen_basis'] = args.reason.strip()
    state['reopen_check_id'] = args.check if failed_check else None
    state['next_action'] = 'Rebuild the affected scope, then hand off again before the next check'
    write_lease(root, 'writer', args.owner)
    save_state(root, state, 'reopen', args.expect_revision)
    return {
        'action': 'reopen',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'previous_stage': previous,
        'previous_lease': lease,
        'failed_check_id': args.check if failed_check else None,
        'scope_changed': bool(args.scope_changed),
    }


def action_block(root, args):
    state = load_state(root)
    if not args.reason.strip():
        raise ValueError('--reason must record the blocking fact and the recovery condition')
    if state.get('stage') != 'blocked':
        state['blocked_from'] = state.get('stage')
    state['stage'] = 'blocked'
    state['next_action'] = args.reason.strip()
    save_state(root, state, 'block', args.expect_revision)
    return {
        'action': 'block',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'blocked_from': state.get('blocked_from'),
    }


def action_unblock(root, args):
    state = load_state(root)
    if state.get('stage') != 'blocked':
        raise ValueError(f"unblock requires stage 'blocked', current stage is {state.get('stage')!r}")
    target = state.get('blocked_from') or 'building'
    if target not in STAGES or target == 'blocked':
        target = 'building'
    state['stage'] = target
    state['next_action'] = 'Resume the interrupted step'
    save_state(root, state, 'unblock', args.expect_revision)
    return {
        'action': 'unblock',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)

    def add(name, help_text):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument('root', type=Path)
        sub.add_argument('--expect-revision', type=int, help='refuse when the file revision differs')
        return sub

    add('show', 'read state, fingerprint, lease and check artifacts')
    claim = add('claim', 'acquire the single writer lease')
    claim.add_argument('--owner', required=True, help='who holds the lease, for the audit trail')
    claim.add_argument('--force', action='store_true')
    claim.add_argument('--reason')
    release = add('release', 'drop the lease without delivering')
    release.add_argument('--owner', required=True, help='must match the active lease owner')
    release.add_argument('--role', choices=['writer', 'checker'])
    concept = add('confirm-concept', 'record concept confirmation as the creator\'s verbatim quote')
    concept.add_argument('--quote', required=True,
                         help='the creator\'s own words, verbatim; the tool records, it cannot verify them')
    concept.add_argument('--anchor',
                         help='optional path to a host transcript; when the quote is found in one of its '
                              'user messages the label is upgraded to quote-matched. Unreadable host '
                              'formats downgrade the label instead of failing. Any "#..." suffix is ignored')
    concept.add_argument('--no-visual', action='store_true', help='this scope needs no separate visual proposal')
    concept.add_argument('--scope-changed', action='store_true', help='invalidate downstream confirmations')
    concept.add_argument(
        '--structure-directions',
        type=int,
        default=None,
        metavar='N',
        help='how many page structures this round asks the creator to compare. 1 means a single structure, so '
             'there is no separate structure decision; 2 or more, or omitting the flag, arms the structure gate '
             'and confirm-structure must record the creator\'s choice before any style choice',
    )
    structure = add('confirm-structure', 'record the chosen page structure as the creator\'s verbatim quote')
    structure.add_argument('--quote', required=True)
    structure.add_argument('--anchor')
    structure.add_argument('--prototype', required=True)
    visual = add('confirm-visual', 'record the selected visual style as the creator\'s verbatim quote')
    visual.add_argument('--quote', required=True)
    visual.add_argument('--anchor')
    visual.add_argument('--prototype', required=True)
    visual.add_argument(
        '--surface-brief',
        help='project design contract; it must record the design.py source and minimum direction evidence',
    )
    authorize = add('authorize-build', 'record explicit development authorization as the creator\'s verbatim quote')
    authorize.add_argument('--quote', required=True)
    authorize.add_argument('--anchor')
    authorize.add_argument('--delegated', action='store_true')
    add('start-build', 'enter building after all gates pass')
    handoff = add('handoff', 'freeze the source after the writer services stopped')
    handoff.add_argument('--stopped-pid', type=int, action='append', default=[])
    handoff.add_argument('--freed-port', type=int, action='append', default=[])
    handoff.add_argument('--service-json', action='append', default=[])
    handoff.add_argument('--note')
    add('start-verify', 'hand the frozen source to the independent checker')
    deliver = add('deliver', 'accept a fingerprint-bound check matrix as delivered')
    deliver.add_argument('--check', required=True, help='check_id produced by site-check')
    reopen = add('reopen', 'void verification or delivery before changing source again')
    reopen.add_argument('--reason', required=True)
    reopen.add_argument('--owner', default='reopen')
    reopen.add_argument('--check', help='failed matrix check_id required when taking back an active Checker lease')
    reopen.add_argument('--scope-changed', action='store_true')
    block = add('block', 'record a hard stop and its recovery condition')
    block.add_argument('--reason', required=True)
    add('unblock', 'leave the blocked stage')
    return parser


ACTIONS = {
    'show': action_show,
    'claim': action_claim,
    'release': action_release,
    'confirm-concept': action_confirm_concept,
    'confirm-structure': action_confirm_structure,
    'confirm-visual': action_confirm_visual,
    'authorize-build': action_authorize_build,
    'start-build': action_start_build,
    'handoff': action_handoff,
    'start-verify': action_start_verify,
    'deliver': action_deliver,
    'reopen': action_reopen,
    'block': action_block,
    'unblock': action_unblock,
}


def main():
    args = build_parser().parse_args()
    root = args.root.expanduser().resolve()
    try:
        if not root.is_dir():
            raise ValueError('Project root must be an existing directory')
        output = ACTIONS[args.action](root, args)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({'error': str(error), 'action': args.action}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
