"""Static, command and matrix checks for collaborative site skills. Python 3.10+, standard library only.

Every run gets a ``check_id`` and, when the project has ``.site`` metadata, is
persisted under ``.site/checks/<check_id>.json`` together with the source
fingerprint.  ``site-builder`` accepts delivery only through a ``matrix``
artifact whose fingerprint still matches the frozen source.

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
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit
import uuid

SKIP = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', '.next', '.cache'}
CHECK_STATUSES = ('passed', 'failed', 'not_run', 'not_applicable')
CHECK_ARTIFACT_DIR = 'checks'
EVIDENCE_KINDS = ('artifact', 'command', 'observation', 'declared')
DEFAULT_EVIDENCE_KIND = 'declared'
VERIFIABLE_EVIDENCE_KINDS = ('artifact', 'command')
PATH_KEYS = ('paths', 'artifacts', 'files', 'screenshots')


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
    data.setdefault('check_id', str(uuid.uuid4()))
    data['artifact'] = write_artifact(root, data)
    if data['artifact'] is None:
        data['artifact_note'] = 'No .site metadata; the evidence was reported but not persisted'
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
    return artifact


def validate_evidence(root, item, identifier, current, cache):
    """Return (evidence, artifacts, problem) for one matrix item."""
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
        if artifact.get('fingerprint') != current or artifact.get('source_changed'):
            problems.append(f'command evidence {check_id!r} was recorded against different source')
            continue
        entries.append({
            'command_check_id': check_id,
            'command': artifact.get('command'),
            'exit_code': artifact.get('exit_code'),
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


def matrix_check(root, payload, label=None, save_evidence=False):
    items = payload.get('items') if isinstance(payload, dict) else payload
    if not isinstance(items, list) or not items:
        raise ValueError('Check matrix needs a non-empty list of items')
    before = fingerprint(root)
    seen = set()
    normalized = []
    artifacts: dict[str, dict] = {}
    failures = []
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
        try:
            evidence, entries, problems = validate_evidence(root, item, identifier, before, {})
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
        for row in entries:
            if 'sha256' in row:
                artifacts[row['path']] = row
        normalized.append({
            'id': identifier,
            'title': str(item.get('title') or identifier),
            'status': status,
            'blocking': item['blocking'],
            'evidence': evidence,
        })
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
        'check_id': str(uuid.uuid4()),
        'created_at': now(),
        'label': label or '',
        'input_fingerprint': before,
        'fingerprint': after,
        'source_changed': before != after,
        'items': normalized,
        'artifacts': artifacts,
        'evidence_failures': failures,
        'counts': counts,
        'blocking_not_passed': blocking_not_passed,
        'status': 'failed' if (blocking_not_passed or failures or before != after) else 'passed',
        'limits': [
            'The matrix verifies that declared evidence exists and is unchanged; it does not execute browser, visual or reopening checks by itself',
            'Only artifact and command evidence can carry a blocking item; declared and observation evidence is reported but never proves a pass',
        ],
        'follow_up': ['Fix blocking failures in site-builder', 'Re-run the whole matrix against a newly frozen fingerprint'],
    }


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
    web = (root / web_root).resolve() if web_root else (root / 'web' if (root / 'web').is_dir() else root)
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
        'check_id': str(uuid.uuid4()),
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
        'check_id': str(uuid.uuid4()),
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
    matrix.add_argument('--save-evidence', action='store_true',
                        help='copy referenced evidence into .site/checks/evidence so re-runs cannot overwrite it')
    args = parser.parse_args()

    try:
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError('Project root must be a directory')
        if args.action == 'static':
            output = static_check(root, args.offline, args.web_root)
        elif args.action == 'run':
            output = run_check(root, args.command, args.timeout)
        else:
            payload = json.loads(Path(args.input).expanduser().read_text(encoding='utf-8'))
            output = matrix_check(root, payload, args.label, args.save_evidence)
        output = finalize(root, output)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1 if output.get('status') == 'failed' else 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
