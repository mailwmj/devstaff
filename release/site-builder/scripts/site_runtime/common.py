"""Deterministic metadata, bounded file access, atomic output and JSON errors."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


class Problem(ValueError):
    def __init__(self, code, message, recovery='Review the input and retry.'):
        super().__init__(message)
        self.code, self.recovery = code, recovery
    def as_dict(self):
        return {'error': str(self), 'message': str(self), 'code': self.code, 'recovery': self.recovery}


class JsonParser(argparse.ArgumentParser):
    def error(self, message):
        raise Problem('INVALID_ARGUMENT', message, 'Run the command with --help.')


def error_result(exc):
    if isinstance(exc, Problem):
        return exc.as_dict()
    text = str(exc)
    for terms, code, recovery in (
        (('changed during', 'fingerprint', 'fresh report'), 'VERSION_CHANGED', 'Cancel the round; plan and verify the current version.'),
        (('mode',), 'MODE_MISMATCH', 'Use project policy, not the mode chosen by a report.'),
        (('contract',), 'CONTRACT_INVALID', 'Repair the applicable contract fields, then run check-contract.'),
        (('site-check', 'sibling'), 'INSTALLATION_INCOMPLETE', 'Run doctor.py and reinstall the complete bundle.'),
        (('state', 'schema'), 'STATE_INVALID', 'Restore a valid backup or use migrate; never delete state to bypass a gate.'),
        (('report',), 'REPORT_INVALID', 'Read the report errors and rerun the necessary checks.'),
    ):
        if any(t in text for t in terms):
            return Problem(code, text, recovery).as_dict()
    return Problem('INVALID_INPUT', text).as_dict()


def metadata_dir(root):
    root = Path(root).resolve()
    found = []
    if root.is_dir():
        for child in root.iterdir():
            if child.name.lower() not in ('.site', '.v3'):
                continue
            if child.is_symlink():
                raise Problem('UNSAFE_METADATA_PATH', 'metadata directory cannot be a symlink')
            if child.is_dir():
                found.append(child)
    if len(found) > 1:
        raise Problem('STATE_PATH_CONFLICT', 'multiple .site/.v3 directories', 'Reconcile both states explicitly; do not silently select one.')
    return found[0] if found else root / '.site'


def project_file(root, relative, must_exist=False):
    root, rel = Path(root).resolve(), Path(relative)
    if rel.is_absolute() or not rel.parts or '..' in rel.parts:
        raise Problem('UNSAFE_PATH', 'expected a project-relative path without ..')
    candidate = root
    for part in rel.parts:
        candidate /= part
        if candidate.is_symlink():
            raise Problem('UNSAFE_PATH', 'symlink input/output is not supported: ' + str(relative))
    if not candidate.resolve().is_relative_to(root):
        raise Problem('UNSAFE_PATH', 'path escapes project root')
    if must_exist and not candidate.is_file():
        raise Problem('MISSING_FILE', 'file not found: ' + str(relative))
    return candidate


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise Problem('UNSAFE_PATH', 'refusing a symlink output')
    fd, name = tempfile.mkstemp(prefix='.tmp-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_json(path):
    path = Path(path)
    if path.is_symlink():
        raise Problem('UNSAFE_PATH', 'JSON file cannot be a symlink')
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise Problem('INVALID_OBJECT', 'expected a JSON object: ' + str(path))
    return value


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def strings(value, name, nonempty=False):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise Problem('INVALID_FIELD', name + ' must be a list of nonempty strings')
    if nonempty and not value:
        raise Problem('INVALID_FIELD', name + ' cannot be empty')
    return value
