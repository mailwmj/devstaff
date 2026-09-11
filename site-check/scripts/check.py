"""Static and command checks for collaborative site skills. Python 3.10+, standard library only."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

SKIP = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', '.next', '.cache'}


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
    args = parser.parse_args()

    try:
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError('Project root must be a directory')
        output = static_check(root, args.offline, args.web_root) if args.action == 'static' else run_check(root, args.command, args.timeout)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1 if output.get('status') == 'failed' else 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
