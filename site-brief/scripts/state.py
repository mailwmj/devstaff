#!/usr/bin/env python3
"""Collaboration state gate for the site skill suite. Python 3.10+, standard library only.

Every ``.site/state.json`` transition after project initialization goes through this
tool.  It replaces "remember the rules" with mechanical checks:

* gate commands refuse a transition whose basis is missing;
* the writer/checker lease makes concurrent Writer and Checker impossible;
* ``handoff`` records stopped PIDs, freed ports and the frozen fingerprint;
* ``start-verify`` refuses unless the source still matches that frozen fingerprint;
* ``deliver`` only accepts a ``site-check`` matrix artifact (``check_id``) whose
  fingerprint equals the current project fingerprint and whose blocking items all
  passed.

What this tool can and cannot guarantee
---------------------------------------

Nothing this tool writes can prove that the creator agreed to anything.  The
creator's judgement lives in their head, and every file here is writable by the
agent the gate is supposed to be restraining.  So the three confirmation gates
(``confirm-concept``, ``confirm-visual``, ``authorize-build``) are **records of
what the agent says the creator said**, not verified facts:

* the caller must pass ``--quote`` with the creator's own words, verbatim;
* an optional ``--anchor`` upgrades the label when the quote can be located in a
  user-role message of a host transcript, and an unreadable host format simply
  downgrades the label instead of failing the gate;
* neither label is forgery-proof, and the record says so in ``basis_note``.

The gate keeps the record honest: verbatim, timestamped, append-only in
revision, and impossible to rewrite silently.  It does not, and must not claim
to, keep the agent honest.  The verification that matters happens when the
creator is shown their own words again at delivery time.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from datetime import datetime, timezone

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
CONSENT_FIELDS = ('concept_consent', 'visual_consent', 'authorization_consent')

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
    for field in ('concept_confirmed', 'visual_confirmed', 'development_authorized', 'delegated'):
        upgraded.setdefault(field, False)
    upgraded.setdefault('runtime', None)
    return upgraded


def save_state(root, state, action, expect_revision=None):
    if expect_revision is not None and state.get('revision') != expect_revision:
        raise ValueError(
            f"Revision conflict: expected {expect_revision}, file has {state.get('revision')}; re-read the project"
        )
    state['schema_version'] = 2
    if 'status' in state:
        state['status'] = state['stage']
    state['revision'] = int(state.get('revision') or 0) + 1
    state['updated_at'] = now()
    state['last_action'] = action
    write_json(root / '.site' / 'state.json', state)
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
        except (OSError, json.JSONDecodeError):
            rows.append({'check_id': path.stem, 'artifact': str(path), 'error': 'unreadable'})
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
    return artifact


def normalize_quote(raw):
    """The creator's own words, verbatim, as the caller recorded them.

    A quote is required because an empty or absent basis is the failure this gate
    exists to catch, and because a verbatim line is what the creator can recognise
    and correct when it is replayed to them.  Length is deliberately not policed:
    "好，就这样" is a legitimate approval for a reversible decision, and any minimum
    here would just be a number to satisfy.
    """
    text = ' '.join((raw or '').split())
    if not text:
        raise ValueError(
            '--quote needs the creator\'s own words, verbatim; a gate never records an empty basis'
        )
    return text


def anchor_text(path):
    """Best-effort transcript text. Returns None when the host shape is unknown.

    Unreadable is a normal outcome, not an error: the caller keeps a
    ``agent-reported`` label and the workflow continues.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if raw[:2] == b'\x1f\x8b':
        try:
            raw = gzip.decompress(raw)
        except OSError:
            return None
    elif raw[:4] == b'\x28\xb5\x2f\xfd':
        try:
            import zstandard  # type: ignore[import-not-found]
        except ImportError:
            return None
        try:
            raw = zstandard.ZstdDecompressor().decompressobj().decompress(raw)
        except Exception:
            return None
    return raw.decode('utf-8', errors='replace')


def anchor_records(text):
    """Parse transcript text into records, tolerating JSON array or JSONL."""
    stripped = text.lstrip()
    if stripped.startswith('['):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return []
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def record_text(message):
    content = message.get('content')
    if isinstance(content, str):
        return content.strip()
    parts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'text' and isinstance(block.get('text'), str):
                parts.append(block['text'])
            elif isinstance(block, str):
                parts.append(block)
    return '\n'.join(parts).strip()


def anchor_user_messages(path):
    """Every user-role message text in a transcript, or None when unreadable."""
    text = anchor_text(path)
    if text is None:
        return None
    found = []
    for record in anchor_records(text):
        message = record.get('message') if isinstance(record.get('message'), dict) else record
        role = str(message.get('role') or '').strip().lower()
        if role in ANCHOR_AGENT_ROLES or role not in ANCHOR_USER_ROLES:
            continue
        body = record_text(message)
        if body:
            found.append(body)
    return found


def locate_anchor(raw, cwd):
    """Resolve the optional ``--anchor`` pointer into (path, readable, note).

    Three outcomes, and only the middle one is a caller error:

    * no anchor supplied -> (None, False, None): label stays ``agent-reported``;
    * anchor supplied and readable -> (path, True, None): the caller must then show
      that the quote really appears, because pointing at a record that lacks it is a
      false claim rather than a downgrade;
    * anchor supplied but unreadable (unknown host format or compression) ->
      (path, False, note): downgrade the label, never block the workflow.

    An unreadable host shape must never fail the gate.  That is the whole point of
    the anchor being optional: host knowledge buys a stronger label, and its absence
    costs nothing but honesty.  Any ``#selector`` suffix is accepted and ignored.
    """
    text = (raw or '').strip()
    if not text:
        return None, False, None
    head, _, _tail = text.partition('#')
    candidate = Path(head).expanduser()
    if not candidate.is_absolute():
        candidate = Path(cwd) / candidate
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ValueError(f'--anchor transcript not found: {head}')
    if anchor_text(resolved) is None:
        return resolved, False, (
            f'The anchor {resolved.name!r} uses a host format this tool cannot read '
            f'(recognised shapes: {", ".join(TRANSCRIPT_SUFFIXES)}; other hosts may compress or '
            'relocate their records). Nothing was verified. The record keeps the agent-reported '
            'label and the workflow continues.'
        )
    return resolved, True, None


def build_consent(args):
    """Assemble the consent record from the caller's quote and optional anchor."""
    quote = normalize_quote(getattr(args, 'quote', None))
    anchor_path, readable, anchor_note = locate_anchor(getattr(args, 'anchor', None), os.getcwd())
    if anchor_path is not None and readable:
        collapsed = ' '.join(quote.split())
        messages = anchor_user_messages(anchor_path) or []
        if not any(collapsed in ' '.join(body.split()) for body in messages):
            raise ValueError(
                f'The quote was not found in a user message of {anchor_path.name}; point --anchor at '
                'the message that carries it, or drop --anchor to record an agent-reported basis'
            )
        basis, note = BASIS_QUOTE_MATCHED, ANCHOR_NOTE
    else:
        basis, note = BASIS_REPORTED, BASIS_NOTE
    return {
        'basis': basis,
        'basis_note': note,
        'quote': quote,
        'quote_sha256': hashlib.sha256(quote.encode('utf-8')).hexdigest(),
        'anchor': str(anchor_path) if anchor_path is not None else None,
        'anchor_note': anchor_note,
        'recorded_at': now(),
    }


def record_consent(state, field, consent, gate):
    """Attach a consent record, refusing to reuse one quote for two gates."""
    for other in CONSENT_FIELDS:
        if other == field:
            continue
        existing = state.get(other)
        if not isinstance(existing, dict):
            continue
        # Compare by content, not by path: copying a file used to defeat this.
        if existing.get('quote_sha256') and existing.get('quote_sha256') == consent['quote_sha256']:
            raise ValueError(
                f'This quote already confirms {other.replace("_consent", "")}; '
                f'{gate} needs its own explicit expression from the creator'
            )
    state[field] = consent


def describe_consent(consent):
    return {
        'action': 'consent',
        'basis': consent['basis'],
        'basis_note': consent['basis_note'],
        'quote': consent['quote'][:200],
        'quote_sha256': consent['quote_sha256'][:16],
        'anchor': consent.get('anchor'),
        'anchor_note': consent.get('anchor_note'),
        'recorded_at': consent['recorded_at'],
    }


def gate_reasons(state, visual_required):
    reasons = []
    if not state.get('concept_confirmed'):
        reasons.append('concept_confirmed is false')
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
        if pid is not None and (not isinstance(pid, int) or pid <= 0):
            raise ValueError('--service-json "pid" must be a positive integer')
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
        'consents': {
            field: (
                dict(state[field], quote=state[field].get('quote', '')[:200])
                if isinstance(state.get(field), dict) else None
            )
            for field in CONSENT_FIELDS
        },
        'checks': [
            dict(row, matches_current_source=row.get('fingerprint') == current)
            for row in check_artifacts(root)
        ],
    }


def action_claim(root, args):
    state = load_state(root)
    existing = read_lease(root)
    if existing and existing.get('role') != 'writer' and not args.force:
        raise ValueError(
            f"Lease is held by {existing.get('role')!r} since {existing.get('acquired_at')}; "
            'finish or release it, or pass --force with --reason'
        )
    if args.force and not args.reason:
        raise ValueError('--force requires --reason so the bypass stays auditable')
    if state.get('stage') == 'delivered' and not args.force:
        raise ValueError('Project is delivered; run reopen before claiming the writer lease again')
    lease = write_lease(root, 'writer', args.owner)
    if args.force:
        state['lease_overrides'] = as_list(state.get('lease_overrides')) + [
            {'at': now(), 'reason': args.reason, 'previous': existing}
        ]
        save_state(root, state, 'claim')
    return {'action': 'claim', 'root': str(root), 'lease': lease, 'forced': bool(args.force)}


def action_release(root, args):
    existing = read_lease(root)
    if not existing:
        raise ValueError('No active lease to release')
    if args.role and existing.get('role') != args.role:
        raise ValueError(f"Lease role is {existing.get('role')!r}, not {args.role!r}")
    clear_lease(root)
    return {'action': 'release', 'root': str(root), 'released': existing}


def action_confirm_concept(root, args):
    state = load_state(root)
    consent = build_consent(args)
    visual_required = not args.no_visual
    if args.scope_changed:
        state['visual_confirmed'] = False
        state['development_authorized'] = False
        state['delegated'] = False
        state.pop('delivery', None)
    record_consent(state, 'concept_consent', consent, 'concept')
    state['concept_confirmed'] = True
    state['visual_required'] = visual_required
    state['concept_basis'] = consent['quote'][:200]
    state['concept_confirmed_at'] = now()
    if state.get('stage') in ('discovering', 'concept_review', None):
        state['stage'] = 'visual_drafting' if visual_required else 'concept_review'
    state['next_action'] = (
        'Produce and review a visual prototype' if visual_required else 'Obtain explicit development authorization'
    )
    save_state(root, state, 'confirm-concept', args.expect_revision)
    return {
        'action': 'confirm-concept',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'concept_confirmed': True,
        'visual_required': visual_required,
        'consent': describe_consent(consent),
    }


def action_confirm_visual(root, args):
    state = load_state(root)
    if not state.get('concept_confirmed'):
        raise ValueError('concept_confirmed is false; confirm the first version before recording a visual choice')
    consent = build_consent(args)
    prototype = Path(args.prototype).expanduser()
    if not prototype.exists():
        raise ValueError(f'--prototype does not exist: {args.prototype}')
    resolved = prototype.resolve()
    inside = resolved.is_relative_to(root)
    record_consent(state, 'visual_consent', consent, 'visual')
    state['visual_confirmed'] = True
    state['visual_basis'] = consent['quote'][:200]
    state['visual_confirmed_at'] = now()
    state['visual_prototype'] = str(resolved)
    if state.get('stage') in ('discovering', 'concept_review', 'visual_drafting', 'visual_review', None):
        state['stage'] = 'visual_review'
    state['next_action'] = 'Obtain explicit development authorization or record a requested change'
    save_state(root, state, 'confirm-visual', args.expect_revision)
    return {
        'action': 'confirm-visual',
        'root': str(root),
        'stage': state['stage'],
        'revision': state['revision'],
        'visual_confirmed': True,
        'prototype': str(resolved),
        'prototype_inside_project': inside,
        'consent': describe_consent(consent),
    }


def action_authorize_build(root, args):
    state = load_state(root)
    if not state.get('concept_confirmed'):
        raise ValueError('concept_confirmed is false; a visual choice alone never authorizes development')
    if state.get('visual_required', True) and not state.get('visual_confirmed'):
        raise ValueError('visual_confirmed is false; show the prototype and get a choice before development')
    consent = build_consent(args)
    record_consent(state, 'authorization_consent', consent, 'authorization')
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
        'consent': describe_consent(consent),
    }


def action_start_build(root, args):
    state = load_state(root)
    lease = require_lease(root, 'writer')
    reasons = gate_reasons(state, state.get('visual_required', True))
    if reasons:
        raise ValueError('Gate not satisfied: ' + '; '.join(reasons))
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
                path = root / '.site' / CHECK_ARTIFACT_DIR / f'{check_id}.json'
                if not path.is_file():
                    problems.append(f'command evidence {check_id}: stored result is missing')
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
    replay = consent_replay(state)
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


def consent_replay(state):
    """The three recorded quotes, for the creator to confirm or disown."""
    labels = {
        'concept_consent': '首版方案确认',
        'visual_consent': '视觉方向确认',
        'authorization_consent': '开发授权',
    }
    replay = []
    for field in CONSENT_FIELDS:
        record = state.get(field)
        if not isinstance(record, dict):
            continue
        # A project already in flight under the older schema stored the wording in
        # "text". Keep replaying it rather than handing the creator a blank line.
        quote = record.get('quote') or record.get('text') or ''
        replay.append({
            'gate': field.replace('_consent', ''),
            'label': labels[field],
            'quote': quote,
            'basis': record.get('basis', BASIS_REPORTED),
            'recorded_at': record.get('recorded_at') or record.get('confirmed_at'),
        })
    return replay


def action_reopen(root, args):
    state = load_state(root)
    lease = read_lease(root)
    if not args.reason.strip():
        raise ValueError('--reason must record why the delivered or verified state is void')
    previous = state.get('stage')
    state['stage'] = 'building'
    state.pop('delivery', None)
    state['writer_release'] = None
    if args.scope_changed:
        state['visual_confirmed'] = False
        state['development_authorized'] = False
        state['delegated'] = False
        state['stage'] = 'visual_drafting' if state.get('visual_required', True) else 'concept_review'
    state['reopen_basis'] = args.reason.strip()
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
    visual = add('confirm-visual', 'record the selected visual direction as the creator\'s verbatim quote')
    visual.add_argument('--quote', required=True)
    visual.add_argument('--anchor')
    visual.add_argument('--prototype', required=True)
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
