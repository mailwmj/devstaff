"""Initialize and inspect projects used by the collaborative site skills. Python 3.10+."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime, timezone
import uuid

SKIP = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', '.next', '.cache'}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        temporary = handle.name
    os.replace(temporary, path)


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
    metadata = root / '.site'
    if metadata.is_symlink():
        raise ValueError('Project metadata must not be a symlink')
    paths = list(project_files(root))
    for name in ('brief.md', 'implementation-plan.md', 'contract.md', 'work.md', 'preview.py'):
        path = metadata / name
        if path.is_file() and not path.is_symlink():
            paths.append(path)
    state_path = metadata / 'state.json'
    digest = hashlib.sha256()
    if state_path.is_file() and not state_path.is_symlink():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        digest.update(json.dumps(
            {'project_id': state.get('project_id'), 'runtime': state.get('runtime')},
            sort_keys=True,
        ).encode())
    for path in sorted(set(paths)):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def read_state(root):
    folder = root / '.site'
    path = folder / 'state.json'
    if folder.is_symlink() or path.is_symlink():
        raise ValueError('Project state must not be a symlink')
    state = json.loads(path.read_text(encoding='utf-8'))
    if state.get('schema_version') not in (1, 2):
        raise ValueError('Unsupported project state; preserve it and inspect project files')
    if not isinstance(state.get('project_id'), str) or not state['project_id']:
        raise ValueError('Damaged project state; preserve it and inspect project files')
    return state


def init_project(destination, template, title, port):
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError('Destination must be absent or a regular directory')
    if destination.exists():
        entries = list(destination.iterdir())
        if any(path.name != '.site' for path in entries):
            raise ValueError('Destination must be empty or contain only .site metadata; existing project files are never overwritten')
        metadata = destination / '.site'
        if metadata.exists() and (not metadata.is_dir() or metadata.is_symlink()):
            raise ValueError('Existing .site metadata must be a regular directory')
    source = Path(__file__).resolve().parent.parent / 'assets' / 'templates' / template
    if not source.is_dir():
        raise ValueError('Template not installed; reinstall the complete site skill suite')

    destination.mkdir(parents=True, exist_ok=True)
    metadata = destination / '.site'
    metadata.mkdir(exist_ok=True)
    state_path = metadata / 'state.json'
    brief_path = metadata / 'brief.md'
    preserved_metadata = state_path.is_file() or brief_path.is_file()
    state = read_state(destination) if state_path.is_file() else None

    shutil.copytree(source, destination, dirs_exist_ok=True)
    preview = metadata / 'preview.py'
    if not preview.exists():
        shutil.copyfile(Path(__file__).with_name('preview.py'), preview)

    index = destination / 'web' / 'index.html'
    index.write_text(
        index.read_text(encoding='utf-8').replace('{{TITLE}}', html.escape(title)),
        encoding='utf-8',
    )
    runtime = {
        'kind': 'local_server',
        'port': port,
        'command': ['python3', '.site/preview.py'],
        'data_paths': [],
    }
    if state is None:
        state = {
            'schema_version': 2,
            'project_id': str(uuid.uuid4()),
            'revision': 1,
            'stage': 'discovering',
            'concept_confirmed': False,
            'visual_confirmed': False,
            'development_authorized': False,
            'delegated': False,
            'runtime': runtime,
            'next_action': 'Clarify the core user, task and first verifiable version',
            'updated_at': now(),
        }
        write_json(state_path, state)
    app = destination / 'web' / 'app.js'
    if app.is_file():
        app.write_text(
            app.read_text(encoding='utf-8').replace('{{PROJECT_ID}}', state['project_id']),
            encoding='utf-8',
        )
    if not brief_path.exists():
        brief_path.write_text(
            f'# {title}\n\n当前为启动基础，尚未确认或实现用户项目。\n\n'
            '## 一句话目标\n\n待澄清。\n\n'
            '## 完整愿景与首版范围\n\n待澄清。\n\n'
            '## 核心用户、场景与任务\n\n待澄清。\n\n'
            '## 已确认决定、假设与暂不包含\n\n待澄清。\n\n'
            '## 体验稿要回答的问题与选定方向\n\n待澄清。\n\n'
            '## 当前进度\n\n正在理解需求。\n',
            encoding='utf-8',
        )
    (destination / '启动.command').write_text(
        '#!/bin/sh\ncd -- "$(dirname -- "$0")"\nexec python3 .site/preview.py\n',
        encoding='utf-8',
    )
    (destination / '启动.command').chmod(0o755)
    (destination / '启动.cmd').write_text(
        '@echo off\r\ncd /d "%~dp0"\r\npy -3 .site\\preview.py\r\npause\r\n',
        encoding='utf-8',
    )
    (destination / '使用说明.md').write_text(
        '# 打开项目\n\n这是启动基础，Agent 完成业务和验收后会更新本说明。\n\n'
        '需要 Python 3.10 或更新版本。Mac 使用 `启动.command`，Windows 使用 `启动.cmd`。'
        '运行后打开终端显示的本机网址；关闭进程即停止服务。\n',
        encoding='utf-8',
    )
    return {
        'project_id': state['project_id'],
        'root': str(destination),
        'stage': state.get('stage', state.get('status')),
        'url': f'http://127.0.0.1:{port}',
        'preserved_metadata': preserved_metadata,
        'runtime_update_required': preserved_metadata and state.get('runtime') != runtime,
        'recommended_runtime': runtime,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    init = commands.add_parser('init')
    init.add_argument('root', type=Path)
    init.add_argument('--template', choices=['static', 'tool'], default='static')
    init.add_argument('--title', default='我的网站')
    init.add_argument('--port', type=int, default=8765)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('root', type=Path)
    args = parser.parse_args()

    try:
        if args.action == 'init':
            if not 1 <= args.port <= 65535:
                raise ValueError('Port must be 1..65535')
            output = init_project(args.root.absolute(), args.template, args.title, args.port)
        else:
            root = args.root.resolve(strict=True)
            if not root.is_dir():
                raise ValueError('Project root must be a directory')
            output = {
                'root': str(root),
                'state': read_state(root) if (root / '.site' / 'state.json').is_file() else None,
                'fingerprint': fingerprint(root),
                'note': 'Inspect does not prove that a process is running or user tasks pass',
            }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
