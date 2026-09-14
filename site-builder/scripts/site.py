"""Initialize and inspect projects used by the collaborative site skills. Python 3.10+."""
import argparse
import hashlib
import html
import json
import os
import shutil
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SKIP = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', '.next', '.cache'}
SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = SKILL_ROOT / 'assets' / 'templates'


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
    """Content fingerprint shared with site-check and the site-brief state gate.

    It deliberately ignores .site/state.json, the lease and the checks directory:
    recording a transition must never invalidate a frozen acceptance fingerprint.
    """
    metadata = root / '.site'
    if metadata.is_symlink():
        raise ValueError('Project metadata must not be a symlink')
    paths = list(project_files(root))
    design = metadata / 'design'
    if design.exists() and (design.is_symlink() or not design.is_dir()):
        raise ValueError('Project design metadata must be a regular directory')
    if design.is_dir():
        paths.extend(path for path in project_files(design) if path.is_file())
    for name in ('brief.md', 'implementation-plan.md', 'contract.md', 'work.md', 'preview.py'):
        path = metadata / name
        if path.is_file() and not path.is_symlink():
            paths.append(path)
    digest = hashlib.sha256()
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
    if state.get('schema_version') not in (1, 2, 3):
        raise ValueError('Unsupported project state; preserve it and inspect project files')
    if not isinstance(state.get('project_id'), str) or not state['project_id']:
        raise ValueError('Damaged project state; preserve it and inspect project files')
    return state


def template_catalog():
    path = TEMPLATE_ROOT / 'catalog.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('templates'), list):
        raise ValueError('Unsupported template catalog; reinstall the complete site Skill suite')
    required = ('id', 'semantic', 'patterns', 'states', 'strengths', 'tradeoffs',
                'reject_conditions', 'validation_commands')
    seen = set()
    for item in data['templates']:
        if any(not item.get(field) for field in required):
            raise ValueError(f'Damaged template metadata: {item.get("id", "unknown")}')
        identifier = item['id']
        if identifier in seen or not identifier.replace('-', '').isalnum():
            raise ValueError(f'Invalid or duplicate template id: {identifier}')
        seen.add(identifier)
        folder = TEMPLATE_ROOT / identifier
        if folder.is_symlink() or not (folder / 'web' / 'index.html').is_file():
            raise ValueError(f'Template files are missing: {identifier}')
    return data


def template_by_id(identifier):
    matches = [item for item in template_catalog()['templates'] if item['id'] == identifier]
    if not matches:
        raise ValueError(f'Unknown template: {identifier}')
    return matches[0]


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
    template_by_id(template)
    source = TEMPLATE_ROOT / template
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
            'schema_version': 3,
            'project_id': str(uuid.uuid4()),
            'revision': 1,
            'stage': 'discovering',
            'concept_confirmed': False,
            'structure_required': False,
            'structure_confirmed': False,
            'visual_required': True,
            'visual_confirmed': False,
            'development_authorized': False,
            'delegated': False,
            'runtime': runtime,
            'delivery_contract': None,
            'delivery_readiness': {'status': 'not_planned'},
            'prototype_handoff': None,
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


RUNNER_BAT_TEMPLATE = """@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

set "SERVE_DIR=."
if exist "web\\index.html" (
    set "SERVE_DIR=web"
)

:: 检测 Python
set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>nul && set "PY_CMD=python"
)
if not defined PY_CMD (
    where python3 >nul 2>nul && set "PY_CMD=python3"
)

if defined PY_CMD (
    for /f %%p in ('%PY_CMD% -c "import socket; print(next(p for p in range(8000, 8100) if (lambda s: (s.connect_ex(('127.0.0.1', p)) != 0, s.close())[0])(socket.socket())))"') do set "PORT=%%p"
    if not defined PORT set "PORT=8000"
    echo 正在启动本地服务: http://localhost:!PORT!
    cd /d "%~dp0\\!SERVE_DIR!"
    start http://localhost:!PORT!
    %PY_CMD% -m http.server !PORT!
    exit /b 0
)

:: 没有 Python 则检测 Node
where npx >nul 2>nul
if !errorlevel! equ 0 (
    echo 未检测到 Python，正在使用 Node.js 启动...
    cd /d "%~dp0\\!SERVE_DIR!"
    start http://localhost:3000
    npx --yes serve .
    exit /b 0
)

echo [提示] 未检测到 Python 或 Node.js 环境。
echo 请先安装 Python (https://www.python.org/) 以便一键启动服务。
echo 您也可以直接双击打开 !SERVE_DIR!\\index.html 浏览页面。
pause
"""

RUNNER_SH_TEMPLATE = """#!/bin/sh
cd -- "$(dirname -- "$0")"

SERVE_DIR="."
if [ -f "web/index.html" ]; then
  SERVE_DIR="web"
fi

cd "$SERVE_DIR" || exit 1

PY_CMD=""
if command -v python3 >/dev/null 2>&1; then
  PY_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PY_CMD="python"
fi

if [ -n "$PY_CMD" ]; then
  PORT=$("$PY_CMD" -c "import socket; print(next(p for p in range(8000, 8100) if (lambda s: (s.connect_ex(('127.0.0.1', p)) != 0, s.close())[0])(socket.socket())))" 2>/dev/null)
  [ -z "$PORT" ] && PORT=8000
  URL="http://localhost:$PORT"
  echo "正在启动本地服务: $URL"
  if command -v xdg-open >/dev/null 2>&1; then
    (sleep 1 && xdg-open "$URL") &
  elif command -v open >/dev/null 2>&1; then
    (sleep 1 && open "$URL") &
  fi
  exec "$PY_CMD" -m http.server "$PORT"
fi

if command -v npx >/dev/null 2>&1; then
  echo "未检测到 Python，正在使用 Node.js 启动..."
  if command -v xdg-open >/dev/null 2>&1; then
    (sleep 1 && xdg-open "http://localhost:3000") &
  elif command -v open >/dev/null 2>&1; then
    (sleep 1 && open "http://localhost:3000") &
  fi
  exec npx --yes serve .
fi

echo "[提示] 未检测到 Python 或 Node.js 环境。"
echo "请先安装 Python (https://www.python.org/) 以便一键运行。"
echo "您也可以直接双击打开 index.html 进行查看。"
exit 1
"""


def make_runner(destination):
    destination = Path(destination).resolve()
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError('Target directory must be an existing directory')

    bat_path = destination / 'start.bat'
    sh_path = destination / 'start.sh'

    bat_path.write_text(RUNNER_BAT_TEMPLATE, encoding='utf-8')
    sh_path.write_text(RUNNER_SH_TEMPLATE, encoding='utf-8')
    try:
        sh_path.chmod(0o755)
    except OSError:
        pass

    return {
        'root': str(destination),
        'scripts': [bat_path.name, sh_path.name],
        'note': 'Generated local runner scripts on-demand upon user confirmation',
    }


def package_project(destination, output_zip=None):
    destination = Path(destination).resolve()
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError('Target directory must be an existing directory')

    if output_zip is None:
        output_zip = destination.parent / f'{destination.name}.zip'
    else:
        output_zip = Path(output_zip).resolve()

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    resolved_output = output_zip.resolve()

    exclude_dirs = {'.git', '.site', 'node_modules', '.venv', '__pycache__', '.idea', '.vscode', '.cache', 'dist', '.next'}
    exclude_files = {'.DS_Store', 'Thumbs.db'}

    packed_files = []
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for root, dirs, files in os.walk(destination, followlinks=False):
            dirs[:] = sorted(
                d for d in dirs
                if d not in exclude_dirs and not d.startswith('.') and not (Path(root) / d).is_symlink()
            )
            for file_name in sorted(files):
                if file_name in exclude_files:
                    continue
                file_path = Path(root) / file_name
                if file_path.resolve() == resolved_output:
                    continue
                if file_path.is_symlink():
                    continue
                arcname = file_path.relative_to(destination).as_posix()
                archive.write(file_path, arcname=arcname)
                packed_files.append(arcname)

    return {
        'root': str(destination),
        'archive': str(output_zip),
        'files_count': len(packed_files),
        'files': packed_files,
        'size_bytes': output_zip.stat().st_size,
    }


def main():
    templates = [item['id'] for item in template_catalog()['templates']]
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    init = commands.add_parser('init')
    init.add_argument('root', type=Path)
    init.add_argument('--template', choices=templates, default='static')
    init.add_argument('--title', default='我的网站')
    init.add_argument('--port', type=int, default=8765)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('root', type=Path)
    commands.add_parser('list-templates')
    inspect_template = commands.add_parser('inspect-template')
    inspect_template.add_argument('template', choices=templates)

    for runner_cmd in ('make-runner', 'helper-start-script'):
        runner = commands.add_parser(runner_cmd)
        runner.add_argument('root', type=Path, default=Path('.'), nargs='?')

    for package_cmd in ('package', 'helper-package'):
        pkg = commands.add_parser(package_cmd)
        pkg.add_argument('root', type=Path, default=Path('.'), nargs='?')
        pkg.add_argument('output', type=Path, default=None, nargs='?')
        pkg.add_argument('--output', '-o', dest='output_flag', type=Path, default=None)

    args = parser.parse_args()

    try:
        if args.action == 'list-templates':
            output = template_catalog()
        elif args.action == 'inspect-template':
            output = template_by_id(args.template)
        elif args.action == 'init':
            if not 1 <= args.port <= 65535:
                raise ValueError('Port must be 1..65535')
            output = init_project(args.root.absolute(), args.template, args.title, args.port)
        elif args.action in ('make-runner', 'helper-start-script'):
            output = make_runner(args.root)
        elif args.action in ('package', 'helper-package'):
            output_path = args.output_flag if args.output_flag is not None else args.output
            output = package_project(args.root, output_path)
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
