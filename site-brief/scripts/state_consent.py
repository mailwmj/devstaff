"""Consent records and best-effort host transcript parsing for the site gates."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone


CONSENT_FIELDS = (
    'concept_consent',
    'structure_consent',
    'visual_consent',
    'authorization_consent',
)
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
TRANSCRIPT_SUFFIXES = ('.jsonl', '.json', '.ndjson')
ANCHOR_AGENT_ROLES = frozenset({'assistant', 'agent', 'model', 'system', 'tool'})
ANCHOR_USER_ROLES = frozenset({'user', 'human'})


def _now():
    return datetime.now(timezone.utc).isoformat()


def _as_list(value):
    return value if isinstance(value, list) else []


def normalize_quote(raw):
    """The creator's own words, verbatim, as the caller recorded them."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(
            '--quote needs the creator\'s own words, verbatim; a gate never records an empty basis'
        )
    return raw


def canonical_quote(raw):
    return ' '.join(str(raw or '').split())


def normalized_quote_digest(record):
    recorded = record.get('quote_normalized_sha256')
    if isinstance(recorded, str) and recorded:
        return recorded
    quote = record.get('quote') or record.get('text')
    if isinstance(quote, str) and quote:
        return hashlib.sha256(canonical_quote(quote).encode('utf-8')).hexdigest()
    legacy = record.get('quote_sha256')
    return legacy if isinstance(legacy, str) else None


def anchor_text(path):
    """Read supported transcript formats, returning None when unreadable."""
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
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return None


def anchor_records(text):
    """Parse transcript text into records, tolerating JSON array or JSONL."""
    stripped = text.strip()
    if not stripped:
        return []
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        if stripped.startswith('['):
            return None
    else:
        if isinstance(payload, dict):
            return [payload]
        return payload if isinstance(payload, list) and all(isinstance(item, dict) for item in payload) else None
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
    return records or None


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


def anchor_user_messages(path, text=None):
    """Every user-role message text in a transcript, or None when unreadable."""
    if text is None:
        text = anchor_text(path)
    if text is None:
        return None
    records = anchor_records(text)
    if records is None:
        return None
    found = []
    recognized_roles = False
    for record in records:
        message = record.get('message') if isinstance(record.get('message'), dict) else record
        role = str(message.get('role') or '').strip().lower()
        recognized_roles |= role in ANCHOR_AGENT_ROLES or role in ANCHOR_USER_ROLES
        if role in ANCHOR_AGENT_ROLES or role not in ANCHOR_USER_ROLES:
            continue
        body = record_text(message)
        if body:
            found.append(body)
    return found if recognized_roles or not records else None


def locate_anchor(raw, cwd):
    """Resolve the optional transcript pointer into (path, readable, note)."""
    if not raw:
        return None, False, None
    head, _, _tail = str(raw).partition('#')
    candidate = Path(head).expanduser()
    if not candidate.is_absolute():
        candidate = Path(cwd) / candidate
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ValueError(f'--anchor transcript not found: {head}')
    text = anchor_text(resolved)
    if text is None or anchor_user_messages(resolved, text) is None:
        try:
            with resolved.open('rb') as handle:
                magic = handle.read(4)
        except OSError:
            magic = b''
        if text is not None:
            detail = 'This transcript does not expose supported JSON/JSONL message roles; the host may use another format.'
        elif magic == b'\x28\xb5\x2f\xfd':
            try:
                import zstandard  # type: ignore[import-not-found]  # noqa: F401
            except ImportError:
                detail = 'This zstd-compressed transcript needs the optional Python package zstandard to be read.'
            else:
                detail = 'This zstd-compressed transcript could not be decompressed or decoded.'
        elif magic[:2] == b'\x1f\x8b':
            detail = 'This gzip-compressed transcript could not be decompressed or decoded.'
        else:
            detail = (
                f'This transcript could not be read as JSON/JSONL '
                f'({", ".join(TRANSCRIPT_SUFFIXES)}); the host may use another format.'
            )
        return resolved, False, (
            f'The anchor {resolved.name!r} cannot be read. {detail} Nothing was verified. '
            'The record keeps the agent-reported label and the workflow continues.'
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
        'quote_normalized_sha256': hashlib.sha256(canonical_quote(quote).encode('utf-8')).hexdigest(),
        'anchor': str(anchor_path) if anchor_path is not None else None,
        'anchor_note': anchor_note,
        'recorded_at': _now(),
    }


def record_consent(state, field, consent, gate):
    """Attach a consent record, refusing to reuse one quote for two gates."""
    for other in CONSENT_FIELDS:
        if other == field:
            continue
        existing = state.get(other)
        if not isinstance(existing, dict):
            continue
        if normalized_quote_digest(existing) == consent['quote_normalized_sha256']:
            raise ValueError(
                f'This quote already confirms {other.replace("_consent", "")}; '
                f'{gate} needs its own explicit expression from the creator'
            )
    for entry in _as_list(state.get('consent_history')):
        if not isinstance(entry, dict) or entry.get('gate') == gate:
            continue
        if normalized_quote_digest(entry) == consent['quote_normalized_sha256']:
            raise ValueError(
                f"This quote already confirmed {entry.get('gate')} in an earlier record; {gate} needs its own "
                'explicit expression from the creator, and recording a gate again does not free an old sentence'
            )
    collapsed = ' '.join(consent['quote'].split())
    earlier = []
    for other in CONSENT_FIELDS:
        if other == field:
            continue
        existing = state.get(other)
        if isinstance(existing, dict) and existing.get('quote'):
            earlier.append((other.replace('_consent', ''), str(existing['quote'])))
    for entry in _as_list(state.get('consent_history')):
        if isinstance(entry, dict) and entry.get('gate') != gate and entry.get('quote'):
            earlier.append((str(entry.get('gate')), str(entry['quote'])))
    for name, quote in earlier:
        other = ' '.join(quote.split())
        if not other:
            continue
        if other in collapsed or collapsed in other:
            raise ValueError(
                f'This quote overlaps the sentence already recorded for {name}; {gate} needs the creator\'s own, '
                'separate expression rather than the same words split or repeated'
            )
    state['consent_history'] = _as_list(state.get('consent_history')) + [{
        'gate': gate,
        'quote': consent['quote'],
        'quote_sha256': consent['quote_sha256'],
        'quote_normalized_sha256': consent['quote_normalized_sha256'],
        'basis': consent['basis'],
        'recorded_at': consent['recorded_at'],
    }]
    state[field] = consent


def describe_consent(consent):
    return {
        'action': 'consent',
        'basis': consent['basis'],
        'basis_note': consent['basis_note'],
        'quote': consent['quote'][:200],
        'quote_sha256': consent['quote_sha256'][:16],
        'quote_normalized_sha256': consent['quote_normalized_sha256'][:16],
        'anchor': consent.get('anchor'),
        'anchor_note': consent.get('anchor_note'),
        'recorded_at': consent['recorded_at'],
    }


def consent_replay(state):
    """Return still-standing consent quotes for delivery replay."""
    labels = {
        'concept_consent': '首版方案确认',
        'structure_consent': '页面结构确认',
        'visual_consent': '视觉风格确认',
        'authorization_consent': '开发授权',
    }
    standing = {
        'concept_consent': 'concept_confirmed',
        'structure_consent': 'structure_confirmed',
        'visual_consent': 'visual_confirmed',
        'authorization_consent': 'development_authorized',
    }
    replay = []
    for field in CONSENT_FIELDS:
        record = state.get(field)
        if not isinstance(record, dict) or not state.get(standing[field]):
            continue
        quote = record.get('quote') or record.get('text') or ''
        replay.append({
            'gate': field.replace('_consent', ''),
            'label': labels[field],
            'quote': quote,
            'basis': record.get('basis', BASIS_REPORTED),
            'recorded_at': record.get('recorded_at') or record.get('confirmed_at'),
        })
    return replay
