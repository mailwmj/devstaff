#!/usr/bin/env python3
"""Regression for the site collaboration state gate. Python 3.10+, standard library only.

Run from anywhere:

    python3 tests/gate_flow.py

It exercises the transition rules that the 2026-09-11 end-to-end report found
violated: evidence-free gate jumps, a Checker started while the Writer's services
still ran, and delivery recorded on top of a blocking failure or changed source.

It then exercises the two mechanisms added afterwards, which is where the same
report's vetoes actually live:

* a gate records the creator's verbatim quote and refuses an empty basis or one
  quote recycled across two gates, compared by content so that copying a file does
  not defeat it.  An ``--anchor`` is an upgrade only: an unreadable host format
  downgrades the label instead of failing, because no gate may depend on host
  internals;
* a blocking matrix item needs ``artifact`` or ``command`` evidence whose files
  still hash the same at delivery time, so a hand-written matrix, a missing
  screenshot or an edited evidence file cannot reach ``delivered``.
* check artifacts are content-addressed, every profile explains its scope, full
  checks cover five release axes, and narrower checks still include a core task;
* lease ownership, failed-check handback, project-local regular prototypes,
  service liveness and compact transition history survive the whole CLI flow.

It also pins the 2026-09-12 finding: choosing among page *structures* was recorded
as a *style* choice, and the style step never happened.  ``--structure-directions``
marks such a round, ``confirm-structure`` records the structure decision on its own,
and ``confirm-visual`` refuses while that decision is pending.

What it deliberately does not test: whether the creator truly meant the quote.  No
local script can decide that.  Delivery replays the quotes for the creator instead
(``consent_replay``), and that hand-back is asserted here.
"""
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable
STATE_TOOL = REPO / 'site-brief' / 'scripts' / 'state.py'
CHECK_TOOL = REPO / 'site-check' / 'scripts' / 'check.py'
SITE_TOOL = REPO / 'site-builder' / 'scripts' / 'site.py'

PASSED = 0
CONCEPT_LINE = '这个第一版可以，就先做这些。'
STRUCTURE_LINE = '结构就按 A 吧，我要左边列表右边详情那种。'
VISUAL_LINE = '第二个挺好看，颜色也不错。'
STYLE_LINE = '那就用第二套配色和字体吧。'
AUTHORIZE_LINE = '就按第二个和刚才说的第一版做吧，开始做。'
# Only ever spoken by the agent, never by the creator.
AGENT_ONLY_LINE = '我建议用第二个方向，你看行不行。'


def call(script, *args):
    return subprocess.run(
        [PY, str(script), *[str(item) for item in args]],
        text=True,
        capture_output=True,
    )


def ok(script, *args):
    global PASSED
    result = call(script, *args)
    if result.returncode != 0:
        raise AssertionError(f"{script.name} {' '.join(map(str, args))} failed: {result.stderr.strip()}")
    PASSED += 1
    return json.loads(result.stdout)


def refused(script, *args):
    global PASSED
    result = call(script, *args)
    if result.returncode != 2:
        raise AssertionError(
            f"{script.name} {' '.join(map(str, args))} should have been refused, exit={result.returncode}"
        )
    PASSED += 1
    try:
        return json.loads(result.stderr)['error']
    except (json.JSONDecodeError, KeyError):
        raise AssertionError(
            f"{script.name} {' '.join(map(str, args))} refused with a non-gate error: {result.stderr.strip()}"
        ) from None


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def listening_socket(port=0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', port))
    sock.listen(1)
    return sock


def dead_pid():
    child = subprocess.Popen([PY, '-c', 'import time; time.sleep(60)'])
    child.kill()
    child.wait()
    return child.pid


def matrix_file(folder, items, profile='full', profile_reason='完整发布验收'):
    path = Path(folder) / 'matrix.json'
    payload = {'items': items}
    payload['profile'] = profile
    payload['profile_reason'] = profile_reason
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return path


def check_artifact(root, check_id):
    return root / '.site' / 'checks' / f'{check_id}.json'


def stage_of(root):
    return json.loads((root / '.site' / 'state.json').read_text(encoding='utf-8'))['stage']


def transcript(folder, name='session.jsonl'):
    """A host-shaped transcript, used only to *upgrade* a consent label.

    Roles matter: a quote found only in an agent message must not upgrade anything.
    """
    path = Path(folder) / name
    records = [
        {'type': 'session', 'version': 3, 'id': 'regression'},
        {'type': 'message', 'id': 'concept', 'message': {
            'role': 'user', 'content': [{'type': 'text', 'text': CONCEPT_LINE}]}},
        {'type': 'message', 'id': 'agent', 'message': {
            'role': 'assistant', 'content': [{'type': 'text', 'text': AGENT_ONLY_LINE}]}},
        {'type': 'message', 'id': 'structure', 'message': {
            'role': 'user', 'content': [{'type': 'text', 'text': STRUCTURE_LINE}]}},
        {'type': 'message', 'id': 'visual', 'message': {
            'role': 'user', 'content': [{'type': 'text', 'text': VISUAL_LINE}]}},
        {'type': 'message', 'id': 'authorize', 'message': {
            'role': 'user', 'content': [{'type': 'text', 'text': AUTHORIZE_LINE}]}},
    ]
    path.write_text('\n'.join(json.dumps(item, ensure_ascii=False) for item in records) + '\n', encoding='utf-8')
    return path


def unreadable_transcript(folder, name='session.v3.jsonl.zstd'):
    """A host record this tool cannot read: the shape that used to kill every gate.

    Zstd magic bytes followed by content that is not valid zstd, so decompression
    fails whether or not a zstd module happens to be installed.
    """
    path = Path(folder) / name
    path.write_bytes(b'\x28\xb5\x2f\xfd' + b'\x00' * 8 + b'not-really-zstd')
    return path


def artifact_evidence(paths, summary='实测产物'):
    return {'kind': 'artifact', 'summary': summary, 'paths': [str(item) for item in paths]}


def main():
    global PASSED
    temp = Path(tempfile.mkdtemp(prefix='site-gate-'))
    root = temp / 'project'
    session = transcript(temp)
    ok(SITE_TOOL, 'init', root, '--template', 'static', '--title', '门禁回归')
    (root / 'prototype.html').write_text('<!doctype html><title>prototype</title>', encoding='utf-8')

    # 1. Every component computes the same content fingerprint.
    inspected = ok(SITE_TOOL, 'inspect', root)
    shown = ok(STATE_TOOL, 'show', root)
    static = ok(CHECK_TOOL, 'static', root)
    assert inspected['fingerprint'] == shown['fingerprint'] == static['fingerprint'], 'fingerprint mismatch'

    # 2. Gates refuse transitions without the required basis.
    refused(STATE_TOOL, 'authorize-build', root, '--quote', AUTHORIZE_LINE)
    refused(STATE_TOOL, 'confirm-visual', root, '--quote', VISUAL_LINE,
            '--prototype', root / 'prototype.html')
    refused(STATE_TOOL, 'start-build', root)
    first_claim = ok(STATE_TOOL, 'claim', root, '--owner', 'builder-a')
    repeated_claim = ok(STATE_TOOL, 'claim', root, '--owner', 'builder-a')
    assert repeated_claim['lease'] == first_claim['lease'], 'same-owner claim must preserve the active lease'
    assert repeated_claim['idempotent'] is True, 'same-owner claim must report that no lease changed'
    assert 'builder-a' in refused(
        STATE_TOOL, 'claim', root, '--owner', 'builder-b'
    ), 'a second writer must not replace the active owner'
    assert 'builder-a' in refused(
        STATE_TOOL, 'release', root, '--owner', 'builder-b'
    ), 'a different owner must not release the active lease'
    forced_claim = ok(
        STATE_TOOL, 'claim', root, '--owner', 'builder-b',
        '--force', '--reason', 'builder-a 已确认异常退出',
    )
    assert forced_claim['lease']['owner'] == 'builder-b' and forced_claim['forced'] is True
    lease_audit = json.loads((root / '.site' / 'state.json').read_text(encoding='utf-8'))['lease_overrides'][-1]
    assert lease_audit['previous']['owner'] == 'builder-a' and lease_audit['reason'] == 'builder-a 已确认异常退出'
    released = ok(STATE_TOOL, 'release', root, '--owner', 'builder-b')
    assert released['released']['owner'] == 'builder-b'
    ok(STATE_TOOL, 'claim', root, '--owner', 'builder-a')
    refused(STATE_TOOL, 'start-build', root)
    refused(STATE_TOOL, 'claim', root, '--owner', 'builder-a', '--force')
    refused(STATE_TOOL, 'handoff', root)
    refused(STATE_TOOL, 'deliver', root, '--check', 'missing')

    # 2b. The basis is the creator's words. The tool records them; it cannot verify them.
    no_quote = call(STATE_TOOL, 'confirm-concept', root)
    assert no_quote.returncode == 2, 'confirm-concept without --quote must be refused'
    PASSED += 1
    refused(STATE_TOOL, 'confirm-concept', root, '--quote', '   ')
    refused(STATE_TOOL, 'confirm-concept', root, '--quote', CONCEPT_LINE,
            '--anchor', f'{temp}/missing.jsonl')
    # An anchor that resolves but does not carry the quote is a false claim, not a downgrade.
    refused(STATE_TOOL, 'confirm-concept', root, '--quote', '我从来没说过这句',
            '--anchor', session)

    # 3. An unreadable host format downgrades the label instead of killing the gate.
    unreadable = unreadable_transcript(temp)
    concept = ok(STATE_TOOL, 'confirm-concept', root, '--quote', CONCEPT_LINE, '--anchor', unreadable,
                 '--structure-directions', 3)
    assert concept['consent']['basis'] == 'agent-reported', 'an unreadable host record must not upgrade'
    assert concept['consent']['anchor_note'], 'the downgrade must be explained, not silent'
    assert concept['consent']['quote'] == CONCEPT_LINE

    # 3a. Choosing among page structures is a different decision from choosing a style.
    # Recording the structure pick as the style choice is what shipped a half-finished
    # prototype on 2026-09-12, so the style gate now refuses while it is pending.
    assert concept['structure_required'] is True, 'comparing structures must arm the structure gate'
    assert 'structure choice is still pending' in refused(
        STATE_TOOL, 'confirm-visual', root, '--quote', VISUAL_LINE,
        '--prototype', root / 'prototype.html')
    refused(STATE_TOOL, 'confirm-structure', root, '--quote', '   ',
            '--prototype', root / 'prototype.html')
    refused(STATE_TOOL, 'confirm-structure', root, '--quote', STRUCTURE_LINE,
            '--prototype', root / 'prototype.html', '--anchor', f'{temp}/missing.jsonl')
    prototype_directory = root / 'prototype-directory'
    prototype_directory.mkdir()
    assert 'regular file' in refused(
        STATE_TOOL, 'confirm-structure', root, '--quote', STRUCTURE_LINE,
        '--prototype', prototype_directory,
    )
    prototype_link = root / 'prototype-link.html'
    prototype_link.symlink_to(root / 'prototype.html')
    assert 'symlink' in refused(
        STATE_TOOL, 'confirm-structure', root, '--quote', STRUCTURE_LINE,
        '--prototype', prototype_link,
    )
    prototype_parent_link = root / 'prototype-parent-link'
    prototype_parent_link.symlink_to(root, target_is_directory=True)
    assert 'parent directory' in refused(
        STATE_TOOL, 'confirm-structure', root, '--quote', STRUCTURE_LINE,
        '--prototype', prototype_parent_link / 'prototype.html',
    )
    outside_prototype = temp / 'outside-prototype.html'
    outside_prototype.write_text('<!doctype html><title>outside</title>', encoding='utf-8')
    assert 'inside the project' in refused(
        STATE_TOOL, 'confirm-structure', root, '--quote', STRUCTURE_LINE,
        '--prototype', outside_prototype,
    )
    structure = ok(STATE_TOOL, 'confirm-structure', root, '--quote', STRUCTURE_LINE,
                   '--prototype', root / 'prototype.html', '--anchor', session)
    assert structure['consent']['basis'] == 'quote-matched'
    assert structure['structure_confirmed'] is True and structure['visual_confirmed'] is False
    # The structure sentence cannot be recycled as the style choice.
    assert 'already confirms' in refused(
        STATE_TOOL, 'confirm-visual', root, '--quote', STRUCTURE_LINE,
        '--prototype', root / 'prototype.html')
    shown_after = ok(STATE_TOOL, 'show', root)
    assert shown_after['structure']['confirmed'] is True, 'show must expose the structure decision'
    assert shown_after['visual']['confirmed'] is False, 'a structure pick is not a style confirmation'
    # Structure settled, style still pending: development stays blocked.
    refused(STATE_TOOL, 'authorize-build', root, '--quote', AUTHORIZE_LINE)

    # 3b. Two visual directions chosen is not development authorization.
    refused(STATE_TOOL, 'authorize-build', root, '--quote', AUTHORIZE_LINE)
    # A readable host record upgrades the label only when a *user* message carries the quote.
    visual = ok(STATE_TOOL, 'confirm-visual', root, '--quote', VISUAL_LINE,
                '--prototype', root / 'prototype.html', '--anchor', session)
    assert visual['consent']['basis'] == 'quote-matched'
    # One quote may not be replayed for a second gate, and copying the file must not help.
    copied = Path(temp) / 'copy-of-session.jsonl'
    copied.write_text(Path(session).read_text(encoding='utf-8'), encoding='utf-8')
    assert 'already confirms' in refused(
        STATE_TOOL, 'confirm-visual', root, '--quote', CONCEPT_LINE,
        '--prototype', root / 'prototype.html', '--anchor', copied)
    assert 'already confirms' in refused(
        STATE_TOOL, 'authorize-build', root, '--quote', VISUAL_LINE)
    refused(STATE_TOOL, 'start-build', root)
    authorized = ok(STATE_TOOL, 'authorize-build', root, '--quote', AUTHORIZE_LINE, '--anchor', session)
    assert authorized['consent']['basis'] == 'quote-matched'
    # An agent's own sentence is never a basis, and an anchor cannot rescue it.
    refused(STATE_TOOL, 'authorize-build', root, '--quote', AGENT_ONLY_LINE, '--anchor', session)
    # Past authorization a structure swap must go through reopen, not a quiet re-record.
    assert 'run reopen' in refused(
        STATE_TOOL, 'confirm-structure', root, '--quote', '还是换成另一个结构吧。',
        '--prototype', root / 'prototype.html')
    # The style gate is symmetric: a swap after authorization is refused as well, so the
    # authorization cannot be left standing over a page it was never given for.
    assert 'run reopen' in refused(
        STATE_TOOL, 'confirm-visual', root, '--quote', '还是换成另一套配色吧。',
        '--prototype', root / 'prototype.html')

    # 4. Writer and Checker cannot hold the project at the same time.
    ok(STATE_TOOL, 'start-build', root)
    assert stage_of(root) == 'building'
    refused(STATE_TOOL, 'claim', root, '--owner', 'builder-b', '--force')  # --force without --reason stays auditable

    # 5. Handoff verifies stopped PIDs and freed ports instead of trusting prose.
    alive = subprocess.Popen([PY, '-c', 'import time; time.sleep(60)'])
    try:
        refused(STATE_TOOL, 'handoff', root, '--stopped-pid', alive.pid, '--freed-port', free_port())
    finally:
        alive.kill()
        alive.wait()
    occupied = listening_socket()
    occupied_port = occupied.getsockname()[1]
    try:
        refused(STATE_TOOL, 'handoff', root, '--stopped-pid', dead_pid(), '--freed-port', occupied_port)
        assert 'inside the project' in refused(
            STATE_TOOL, 'handoff', root,
            '--service-json', json.dumps({
                'owner': 'formal', 'pid': os.getpid(), 'port': occupied_port, 'root': str(temp),
            }),
        )
        assert 'pid' in refused(
            STATE_TOOL, 'handoff', root,
            '--service-json', json.dumps({'owner': 'formal', 'port': occupied_port, 'root': str(root)}),
        ), 'a registered service must identify its live process'
        assert 'not running' in refused(
            STATE_TOOL, 'handoff', root,
            '--service-json', json.dumps({
                'owner': 'formal', 'pid': dead_pid(), 'port': occupied_port, 'root': str(root),
            }),
        ), 'a registered service PID must still be alive'
        assert 'not listening' in refused(
            STATE_TOOL, 'handoff', root,
            '--service-json', json.dumps({
                'owner': 'formal', 'pid': os.getpid(), 'port': free_port(), 'root': str(root),
            }),
        ), 'a registered service port must actually be listening'
        # A registered service may stay up, but only inside the project root.
        ok(
            STATE_TOOL, 'handoff', root,
            '--stopped-pid', dead_pid(),
            '--freed-port', free_port(),
            '--service-json', json.dumps({
                'owner': 'formal', 'pid': os.getpid(), 'port': occupied_port, 'root': str(root),
            }),
        )
    finally:
        occupied.close()

    release = json.loads((root / '.site' / 'state.json').read_text(encoding='utf-8'))['writer_release']
    assert release['services'][0]['port'] == occupied_port and release['freed_ports']

    # 6. Source changing after handoff voids the freeze.
    (root / 'web' / 'index.html').write_text(
        (root / 'web' / 'index.html').read_text(encoding='utf-8') + '\n<!-- late write -->\n', encoding='utf-8'
    )
    refused(STATE_TOOL, 'start-verify', root)
    ok(STATE_TOOL, 'handoff', root, '--stopped-pid', dead_pid(), '--freed-port', free_port())

    # 7. Delivery needs a fingerprint-bound matrix with every blocking item passed.
    ok(STATE_TOOL, 'start-verify', root)
    assert stage_of(root) == 'verifying'
    assert 'failed check' in refused(
        STATE_TOOL, 'reopen', root, '--reason', '还没有 Checker 结果'
    ), 'an active Checker must not be replaced without a failed matrix result'
    assert 'reopen --check' in refused(
        STATE_TOOL, 'claim', root, '--owner', 'builder-b', '--force', '--reason', '绕过 Checker'
    ), 'force claim must not bypass an active verification lease'
    assert 'reopen --check' in refused(
        STATE_TOOL, 'release', root, '--owner', 'builder-a'
    ), 'release must not bypass an active verification lease'
    (root / 'evidence').mkdir()
    (root / 'evidence' / 'desktop.png').write_bytes(b'\x89PNG\r\n\x1a\nscreenshot')
    (root / 'evidence' / 'clipboard.json').write_text('{"copied": "linlaoshi_nature_test"}', encoding='utf-8')

    def passing_items():
        """Command evidence must belong to the source the matrix fingerprints."""
        command = ok(CHECK_TOOL, 'run', root, '--', PY, '-c', 'print("build ok")')
        return [
            {'id': 'static', 'axis': 'static_build', 'title': '静态引用', 'status': 'passed', 'blocking': True,
             'evidence': {'kind': 'command', 'summary': 'check.py run 退出 0', 'commands': [command['check_id']]}},
            {'id': 'core-task', 'axis': 'core_task', 'title': '核心任务', 'status': 'passed', 'blocking': True,
             'evidence': artifact_evidence(['evidence/desktop.png', 'evidence/clipboard.json'])},
            {'id': 'visual-desktop', 'axis': 'visual_desktop', 'title': '桌面视觉',
             'status': 'passed', 'blocking': True,
             'evidence': artifact_evidence(['evidence/desktop.png'])},
            {'id': 'visual-mobile', 'axis': 'visual_mobile', 'title': '手机视觉',
             'status': 'passed', 'blocking': True,
             'evidence': artifact_evidence(['evidence/desktop.png'])},
            {'id': 'reopen', 'axis': 'reopen', 'title': '再次打开', 'status': 'passed', 'blocking': True,
             'evidence': artifact_evidence(['evidence/clipboard.json'])},
            {'id': 'favicon', 'axis': 'static_build', 'title': 'favicon', 'status': 'failed', 'blocking': False,
             'evidence': {'kind': 'declared', 'summary': '冷启动 404'}},
        ]

    assert 'profile_reason' in refused(
        CHECK_TOOL, 'matrix', root,
        '--input', matrix_file(temp, passing_items(), 'targeted', ''),
    ), 'every check profile must explain why that scope was selected'
    assert '"axis"' in refused(
        CHECK_TOOL, 'matrix', root,
        '--input', matrix_file(temp, [
            {'id': 'missing-axis', 'status': 'passed', 'blocking': True,
             'evidence': artifact_evidence(['evidence/desktop.png'])},
        ], 'smoke', '验证矩阵字段'),
    ), 'every matrix item must name its verification axis'
    assert 'required blocking axes' in refused(
        CHECK_TOOL, 'matrix', root,
        '--input', matrix_file(temp, [
            {'id': 'core-only', 'axis': 'core_task', 'status': 'passed', 'blocking': True,
             'evidence': artifact_evidence(['evidence/desktop.png'])},
        ], 'full', '故意缺轴的完整检查'),
    ), 'full verification must cover every release axis'
    static_only = passing_items()[0]
    for narrow_profile in ('targeted', 'smoke'):
        assert 'core_task' in refused(
            CHECK_TOOL, 'matrix', root,
            '--input', matrix_file(temp, [static_only], narrow_profile, '故意漏掉核心任务'),
        ), f'{narrow_profile} verification must include an affected core task'

    # Command evidence from an earlier round is stale once the source changed.
    stale_command = ok(CHECK_TOOL, 'run', root, '--', PY, '-c', 'print("stale build")')
    (root / 'evidence' / 'note.txt').write_text('source moved on after that command', encoding='utf-8')
    stale = call(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, [
        {'id': 'static', 'axis': 'core_task', 'status': 'passed', 'blocking': True,
         'evidence': {'kind': 'command', 'summary': '旧命令', 'commands': [stale_command['check_id']]}},
    ], 'smoke', '验证旧命令凭据'))
    assert stale.returncode == 1
    stale_reason = json.loads(stale.stdout)['evidence_failures'][0]['reason']
    assert 'different source' in stale_reason, stale_reason
    PASSED += 1

    # 7a. A blocking item declared with prose is not evidence.
    prose = [{'id': 'core-task', 'axis': 'core_task', 'title': '核心任务', 'status': 'passed', 'blocking': True,
              'evidence': '我实际操作过，成功了'}]
    prose_matrix = call(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, prose, 'smoke', '验证文字声明'))
    assert prose_matrix.returncode == 1, 'prose evidence must not satisfy a blocking item'
    prose_result = json.loads(prose_matrix.stdout)
    assert prose_result['status'] == 'failed' and prose_result['evidence_failures']
    assert any('declared' in row['reason'] for row in prose_result['evidence_failures'])
    refused(STATE_TOOL, 'deliver', root, '--check', prose_result['check_id'])
    PASSED += 3

    # 7b. Naming a screenshot that does not exist fails instead of passing.
    ghost = [{'id': 'core-task', 'axis': 'core_task', 'title': '核心任务', 'status': 'passed', 'blocking': True,
              'evidence': artifact_evidence(['evidence/missing.png'])}]
    ghost_matrix = call(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, ghost, 'smoke', '验证缺失证据'))
    assert ghost_matrix.returncode == 1, 'a missing artifact must not pass'
    ghost_result = json.loads(ghost_matrix.stdout)
    assert 'does not exist' in ghost_result['evidence_failures'][0]['reason']
    refused(STATE_TOOL, 'deliver', root, '--check', ghost_result['check_id'])
    # Evidence may not point outside the project either.
    outside = temp / 'outside.png'
    outside.write_bytes(b'x')
    escaped = call(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, [
        {'id': 'core-task', 'axis': 'core_task', 'status': 'passed', 'blocking': True,
         'evidence': artifact_evidence([outside])},
    ], 'smoke', '验证越界证据'))
    assert escaped.returncode == 1 and 'outside the project' in json.loads(escaped.stdout)['evidence_failures'][0]['reason']
    PASSED += 3

    passing = passing_items()
    first = ok(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, passing), '--save-evidence')
    assert first['status'] == 'passed' and first['artifact'] == f".site/checks/{first['check_id']}.json"
    assert check_artifact(root, first['check_id']).is_file()
    assert first['evidence_failures'] == []
    assert all(row['evidence']['verified'] for row in first['items'] if row['blocking'])
    assert 'failed check matrix' in refused(
        STATE_TOOL, 'reopen', root, '--reason', '不能拿通过结果返工', '--check', first['check_id']
    ), 'reopen must not use a passing matrix to take back the Checker lease'
    first_path = check_artifact(root, first['check_id'])
    first_bytes = first_path.read_bytes()
    edited_first = json.loads(first_bytes)
    edited_first['label'] = 'edited after the check'
    first_path.write_text(json.dumps(edited_first, ensure_ascii=False), encoding='utf-8')
    assert 'content digest' in refused(
        STATE_TOOL, 'deliver', root, '--check', first['check_id']
    ), 'editing a stored matrix must invalidate its content-addressed check_id'
    first_path.write_bytes(first_bytes)
    command_id = first['items'][0]['evidence']['items'][0]['command_check_id']
    command_path = check_artifact(root, command_id)
    command_bytes = command_path.read_bytes()
    edited_command = json.loads(command_bytes)
    edited_command['stdout'] = 'edited after the matrix referenced it'
    command_path.write_text(json.dumps(edited_command, ensure_ascii=False), encoding='utf-8')
    assert 'content digest' in refused(
        STATE_TOOL, 'deliver', root, '--check', first['check_id']
    ), 'editing referenced command evidence must invalidate delivery'
    command_path.write_bytes(command_bytes)
    targeted = ok(
        CHECK_TOOL, 'matrix', root,
        '--input', matrix_file(temp, passing_items(), 'targeted', '只验证导出交互'),
    )
    assert targeted['profile'] == 'targeted'
    assert targeted['profile_reason'] == '只验证导出交互'
    archived = root / '.site' / 'checks' / 'evidence' / 'desktop.png'
    assert archived.is_file(), 'save-evidence must archive the screenshot delivery re-checks'

    # A blocking failure keeps the project in verifying.
    failing = passing + [
        {'id': 'contrast', 'axis': 'visual_desktop', 'title': '对比度', 'status': 'failed', 'blocking': True,
         'evidence': {'kind': 'artifact', 'summary': '4.17:1 < 4.5:1', 'paths': ['evidence/contrast.txt']}},
    ]
    (root / 'evidence' / 'contrast.txt').write_text('#627b78 on #f2f6f4 = 4.17:1', encoding='utf-8')
    second = call(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, failing))
    assert second.returncode == 1, 'a blocked matrix must exit non-zero'
    second = json.loads(second.stdout)
    assert second['status'] == 'failed' and second['blocking_not_passed'] == ['contrast']
    refused(STATE_TOOL, 'deliver', root, '--check', second['check_id'])
    assert stage_of(root) == 'verifying', 'a blocking failure must not reach delivered'
    PASSED += 2

    # A matrix item with no evidence at all fails instead of passing quietly.
    missing_evidence = call(
        CHECK_TOOL, 'matrix', root,
        '--input', matrix_file(temp, [
            {'id': 'x', 'axis': 'core_task', 'status': 'passed', 'blocking': True},
        ], 'smoke', '验证缺少证据'),
    )
    assert missing_evidence.returncode == 1
    missing_result = json.loads(missing_evidence.stdout)
    assert missing_result['status'] == 'failed' and 'needs evidence' in missing_result['evidence_failures'][0]['reason']
    PASSED += 1
    # An unknown evidence kind fails instead of being treated as a claim.
    unknown_kind = call(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, [
        {'id': 'x', 'axis': 'core_task', 'status': 'passed', 'blocking': True,
         'evidence': {'kind': 'guessed', 'summary': 'x'}},
    ], 'smoke', '验证未知证据类型'))
    assert unknown_kind.returncode == 1
    assert 'kind must be one of' in json.loads(unknown_kind.stdout)['evidence_failures'][0]['reason']
    PASSED += 1

    # A source edit after the check voids the acceptance result.
    third = ok(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, passing_items()))
    (root / 'web' / 'style.css').write_text(
        (root / 'web' / 'style.css').read_text(encoding='utf-8') + '\n/* late */\n', encoding='utf-8'
    )
    error = refused(STATE_TOOL, 'deliver', root, '--check', third['check_id'])
    assert 'Source changed' in error
    assert stage_of(root) == 'verifying'

    # 7c. Overwriting the archived evidence after the check voids delivery.
    fourth = ok(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, passing_items()), '--save-evidence')
    tampered = root / '.site' / 'checks' / 'evidence' / 'desktop.png'
    original = tampered.read_bytes()
    tampered.write_bytes(b'\x89PNG\r\n\x1a\nedited later')
    error = refused(STATE_TOOL, 'deliver', root, '--check', fourth['check_id'])
    assert 'evidence changed after the check' in error, error
    tampered.write_bytes(original)
    assert ok(STATE_TOOL, 'deliver', root, '--check', fourth['check_id'])['stage'] == 'delivered'

    # 7d. A hand-written matrix that reuses a real fingerprint is not acceptance.
    ok(STATE_TOOL, 'reopen', root, '--reason', '下一轮修复')
    ok(STATE_TOOL, 'handoff', root, '--stopped-pid', dead_pid(), '--freed-port', free_port())
    ok(STATE_TOOL, 'start-verify', root)
    forged = ok(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, passing_items()))
    forged_path = check_artifact(root, forged['check_id'])
    (forged_path).write_text(json.dumps({
        'schema_version': 1, 'kind': 'matrix', 'check_id': forged['check_id'], 'status': 'passed',
        'fingerprint': forged['fingerprint'],
        'items': [{'id': 'core-task', 'status': 'passed', 'blocking': True, 'evidence': '我说通过了'}],
    }, ensure_ascii=False), encoding='utf-8')
    error = refused(STATE_TOOL, 'deliver', root, '--check', forged['check_id'])
    assert 'content digest' in error, error
    # An emptied artifact map is equally refused instead of passing on nothing.
    (forged_path).write_text(json.dumps({
        'schema_version': 1, 'kind': 'matrix', 'check_id': forged['check_id'], 'status': 'passed',
        'fingerprint': forged['fingerprint'], 'artifacts': {},
        'items': [{'id': 'core-task', 'status': 'passed', 'blocking': True,
                   'evidence': {'kind': 'artifact', 'summary': 'x', 'items': [], 'verified': True}}],
    }, ensure_ascii=False), encoding='utf-8')
    assert 'content digest' in refused(STATE_TOOL, 'deliver', root, '--check', forged['check_id'])

    # 8. Delivery through the frozen matrix, then reopen for the next round.
    recovery = call(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, passing_items() + [
        {'id': 'contrast', 'axis': 'visual_desktop', 'title': '对比度', 'status': 'failed', 'blocking': True,
         'evidence': artifact_evidence(['evidence/contrast.txt'])},
    ]))
    assert recovery.returncode == 1
    recovery = json.loads(recovery.stdout)
    reopened = ok(
        STATE_TOOL, 'reopen', root, '--reason', '修复对比度并重新验收',
        '--check', recovery['check_id'],
    )
    assert reopened['failed_check_id'] == recovery['check_id']
    PASSED += 1
    ok(STATE_TOOL, 'handoff', root, '--stopped-pid', dead_pid(), '--freed-port', free_port())
    ok(STATE_TOOL, 'start-verify', root)
    final = ok(CHECK_TOOL, 'matrix', root, '--input', matrix_file(temp, passing_items()), '--save-evidence')
    delivered = ok(STATE_TOOL, 'deliver', root, '--check', final['check_id'])
    assert delivered['stage'] == 'delivered' and delivered['delivery']['check_id'] == final['check_id']
    # Delivery hands the creator their own words back: the only real check on consent.
    assert [entry['quote'] for entry in delivered['consent_replay']] == [
        CONCEPT_LINE, STRUCTURE_LINE, VISUAL_LINE, AUTHORIZE_LINE
    ], 'delivery must replay every recorded quote verbatim, structure choice included'
    assert [entry['label'] for entry in delivered['consent_replay']] == [
        '首版方案确认', '页面结构确认', '视觉风格确认', '开发授权'
    ], 'the structure pick and the style pick must be replayed as two separate decisions'
    refused(STATE_TOOL, 'claim', root, '--owner', 'builder-b')
    # A delivered project cannot be re-authorized or re-decided in place: the check and
    # the delivery must be voided through reopen first.
    assert 'authorize-build cannot run' in refused(
        STATE_TOOL, 'authorize-build', root, '--quote', '就按新的那套再授权一次。')
    # `block` records a blockage; it is not a one-command detour around the guards.
    ok(STATE_TOOL, 'block', root, '--reason', '临时记录一下')
    assert 'cannot be re-decided at stage' in refused(
        STATE_TOOL, 'confirm-visual', root, '--quote', '换成第三套配色。',
        '--prototype', root / 'prototype.html')
    assert 'cannot be re-decided at stage' in refused(
        STATE_TOOL, 'confirm-structure', root, '--quote', '换成 C 结构。',
        '--prototype', root / 'prototype.html')
    assert 'cannot run at stage' in refused(STATE_TOOL, 'confirm-concept', root, '--quote', '再确认一次。')
    ok(STATE_TOOL, 'unblock', root)
    assert stage_of(root) == 'delivered', 'unblock must return to the stage it was blocked from'
    ok(STATE_TOOL, 'reopen', root, '--reason', '用户要求改首屏文案')
    assert stage_of(root) == 'building'
    # The issued consent trail stays readable for the audit.
    audit = json.loads((root / '.site' / 'state.json').read_text(encoding='utf-8'))
    for field in ('concept_consent', 'structure_consent', 'visual_consent', 'authorization_consent'):
        record = audit[field]
        assert record['basis'] in ('agent-reported', 'quote-matched')
        assert record['quote_sha256'] == hashlib.sha256(record['quote'].encode('utf-8')).hexdigest()
        assert record['basis_note'], 'every consent record must state that it is not a proof'
    build_transition = next(row for row in audit['transition_history'] if row['action'] == 'start-build')
    assert build_transition['actor'] == 'builder-a' and build_transition['lease_role'] == 'writer'
    PASSED += 1

    # 9. A project without .site is never initialized or rewritten by the checker.
    third_party = temp / 'third-party'
    third_party.mkdir()
    (third_party / 'index.html').write_text('<!doctype html><title>x</title>', encoding='utf-8')
    bare = ok(CHECK_TOOL, 'static', third_party)
    assert bare['artifact'] is None and not (third_party / '.site').exists()

    # 9b. Verbatim means the exact caller text; normalization is separate and is
    # used only to detect a repeated sentence across formatting differences.
    exact = temp / 'exact-quote'
    exact_quote = '这个第一版可以。\n  就这样做。'
    canonical_quote = '这个第一版可以。 就这样做。'
    ok(SITE_TOOL, 'init', exact, '--template', 'static', '--title', '原话回归')
    ok(STATE_TOOL, 'confirm-concept', exact, '--quote', exact_quote, '--structure-directions', 1)
    exact_state = json.loads((exact / '.site' / 'state.json').read_text(encoding='utf-8'))
    exact_record = exact_state['concept_consent']
    assert exact_record['quote'] == exact_quote, 'confirmation text must preserve whitespace and newlines exactly'
    assert exact_record['quote_sha256'] == hashlib.sha256(exact_quote.encode('utf-8')).hexdigest()
    assert exact_record['quote_normalized_sha256'] == hashlib.sha256(canonical_quote.encode('utf-8')).hexdigest()
    transition = exact_state['transition_history'][-1]
    assert transition['action'] == 'confirm-concept'
    assert transition['before']['stage'] == 'discovering' and transition['after']['stage'] == 'visual_drafting'
    assert 'transition_history' not in transition['before'] and 'transition_history' not in transition['after']
    (exact / 'prototype.html').write_text('<!doctype html><title>prototype</title>', encoding='utf-8')
    assert 'already confirms' in refused(
        STATE_TOOL, 'confirm-visual', exact, '--quote', canonical_quote,
        '--prototype', exact / 'prototype.html',
    ), 'whitespace changes must not make one consent sentence reusable at another gate'
    PASSED += 1

    # 10. A legacy schema v1 record is upgraded on first write and never implies a gate.
    legacy = temp / 'legacy'
    (legacy / '.site').mkdir(parents=True)
    (legacy / '.site' / 'state.json').write_text(json.dumps({
        'schema_version': 1,
        'project_id': 'legacy-id',
        'status': 'ready',
        'next_action': '旧记录',
        'runtime': {'kind': 'local_server', 'port': 8765},
        'custom_legacy_field': 'keep me',
    }), encoding='utf-8')
    ok(STATE_TOOL, 'confirm-concept', legacy, '--quote', CONCEPT_LINE, '--no-visual')
    migrated = json.loads((legacy / '.site' / 'state.json').read_text(encoding='utf-8'))
    assert migrated['schema_version'] == 2 and migrated['stage'] == 'concept_review'
    assert migrated['concept_confirmed'] is True and migrated['runtime']['port'] == 8765
    assert migrated['custom_legacy_field'] == 'keep me'
    assert migrated['development_authorized'] is False and migrated['visual_confirmed'] is False
    refused(STATE_TOOL, 'start-build', legacy)
    refused(STATE_TOOL, 'claim', legacy, '--owner', 'builder-c', '--force')
    PASSED += 3
    # A scope that declared no visual proposal has no structure step either.
    (legacy / 'prototype.html').write_text('<!doctype html><title>x</title>', encoding='utf-8')
    assert 'no structure choice' in refused(
        STATE_TOOL, 'confirm-structure', legacy, '--quote', STRUCTURE_LINE,
        '--prototype', legacy / 'prototype.html')

    # 10b. One structure means no separate structure decision, and re-deciding the
    # structure voids a style choice that was made for the page that no longer exists.
    single = temp / 'single-direction'
    ok(SITE_TOOL, 'init', single, '--template', 'static', '--title', '单结构回归')
    (single / 'prototype.html').write_text('<!doctype html><title>prototype</title>', encoding='utf-8')
    one = ok(STATE_TOOL, 'confirm-concept', single, '--quote', CONCEPT_LINE, '--structure-directions', 1)
    assert one['structure_required'] is False, 'one structure arms no structure gate'
    assert ok(STATE_TOOL, 'confirm-visual', single, '--quote', VISUAL_LINE,
              '--prototype', single / 'prototype.html')['visual_confirmed'] is True
    changed = ok(STATE_TOOL, 'confirm-structure', single, '--quote', STRUCTURE_LINE,
                 '--prototype', single / 'prototype.html')
    assert changed['invalidated_stale_visual_choice'] is True, 'the invalidation must be reported'
    assert changed['visual_confirmed'] is False, 'a style chosen for the old structure cannot survive'
    refused(STATE_TOOL, 'authorize-build', single, '--quote', AUTHORIZE_LINE)
    # `--scope-changed` also clears the structure decision, not just the style one.
    ok(STATE_TOOL, 'confirm-visual', single, '--quote', STYLE_LINE,
       '--prototype', single / 'prototype.html')
    rescoped = ok(STATE_TOOL, 'confirm-concept', single, '--quote', '范围改了，重来一版。',
                  '--scope-changed', '--structure-directions', 1)
    assert rescoped['stage'] == 'visual_drafting' and rescoped['structure_required'] is False
    after = json.loads((single / '.site' / 'state.json').read_text(encoding='utf-8'))
    assert after['structure_confirmed'] is False and after['visual_confirmed'] is False

    # 10c. The two-step rule fails closed: a round that does not say how many structures
    # it showed is treated as several, so the structure decision must be recorded first.
    undeclared = temp / 'undeclared'
    ok(SITE_TOOL, 'init', undeclared, '--template', 'static', '--title', '未声明回归')
    (undeclared / 'prototype.html').write_text('<!doctype html><title>prototype</title>', encoding='utf-8')
    guess = ok(STATE_TOOL, 'confirm-concept', undeclared, '--quote', CONCEPT_LINE)
    assert guess['structure_required'] is True, 'an undeclared round must fail closed'
    assert 'structure choice is still pending' in refused(
        STATE_TOOL, 'confirm-visual', undeclared, '--quote', STRUCTURE_LINE,
        '--prototype', undeclared / 'prototype.html')
    refused(STATE_TOOL, 'confirm-concept', undeclared, '--quote', CONCEPT_LINE, '--structure-directions', 0)
    refused(STATE_TOOL, 'confirm-concept', undeclared, '--quote', CONCEPT_LINE, '--structure-directions', -2)
    assert 'drop one of the two' in refused(
        STATE_TOOL, 'confirm-concept', undeclared, '--quote', CONCEPT_LINE,
        '--no-visual', '--structure-directions', 3)
    # An explicit single-structure declaration is the only way to skip the structure gate.
    declared = ok(STATE_TOOL, 'confirm-concept', undeclared, '--quote', CONCEPT_LINE,
                  '--structure-directions', 1)
    assert declared['structure_required'] is False
    ok(STATE_TOOL, 'confirm-visual', undeclared, '--quote', VISUAL_LINE,
       '--prototype', undeclared / 'prototype.html')

    # 10d. Recording a gate again does not free an old sentence for another gate.
    recycled = temp / 'recycled'
    ok(SITE_TOOL, 'init', recycled, '--template', 'static', '--title', '复用回归')
    (recycled / 'prototype.html').write_text('<!doctype html><title>prototype</title>', encoding='utf-8')
    ok(STATE_TOOL, 'confirm-concept', recycled, '--quote', CONCEPT_LINE)
    ok(STATE_TOOL, 'confirm-concept', recycled, '--quote', '换个说法再确认一次方案。')
    assert 'earlier record' in refused(
        STATE_TOOL, 'confirm-structure', recycled, '--quote', CONCEPT_LINE,
        '--prototype', recycled / 'prototype.html')
    # The superseded sentence stays readable for the audit instead of vanishing.
    history = json.loads((recycled / '.site' / 'state.json').read_text(encoding='utf-8'))['consent_history']
    assert [row['quote'] for row in history] == [CONCEPT_LINE, '换个说法再确认一次方案。'], history

    # 10e. A core-scope change voids the concept too, and voided quotes leave the replay:
    # the delivery hand-back must never present an abandoned sentence as current.
    scoped = temp / 'scoped'
    ok(SITE_TOOL, 'init', scoped, '--template', 'static', '--title', '范围变更回归')
    (scoped / 'prototype.html').write_text('<!doctype html><title>prototype</title>', encoding='utf-8')
    ok(STATE_TOOL, 'confirm-concept', scoped, '--quote', CONCEPT_LINE, '--structure-directions', 1)
    ok(STATE_TOOL, 'confirm-visual', scoped, '--quote', VISUAL_LINE, '--prototype', scoped / 'prototype.html')
    assert len(ok(STATE_TOOL, 'show', scoped)['consent_replay']) == 2, 'standing decisions are replayed'
    ok(STATE_TOOL, 'reopen', scoped, '--reason', '核心范围变了', '--scope-changed')
    rescope_state = json.loads((scoped / '.site' / 'state.json').read_text(encoding='utf-8'))
    assert rescope_state['concept_confirmed'] is False, 'a core-scope change voids the concept'
    assert rescope_state['visual_confirmed'] is False
    refused(STATE_TOOL, 'authorize-build', scoped, '--quote', AUTHORIZE_LINE)
    assert ok(STATE_TOOL, 'show', scoped)['consent_replay'] == [], (
        'a voided decision must not be replayed as standing consent'
    )

    # 10f. reopen is not a way into building: a project with nothing recorded cannot hand
    # itself a writer lease and stage its way to delivered with every gate false.
    virgin = temp / 'virgin'
    ok(SITE_TOOL, 'init', virgin, '--template', 'static', '--title', '空项目回归')
    assert 'Nothing to reopen' in refused(STATE_TOOL, 'reopen', virgin, '--reason', '随便一个理由')
    assert stage_of(virgin) == 'discovering'
    refused(STATE_TOOL, 'handoff', virgin, '--stopped-pid', dead_pid(), '--freed-port', free_port())

    # 10g. A scope that declares no visual step has no design decisions left standing, so
    # a structure quote cannot keep being replayed for a decision the project dropped.
    downgraded = temp / 'downgraded'
    ok(SITE_TOOL, 'init', downgraded, '--template', 'static', '--title', '降级回归')
    (downgraded / 'prototype.html').write_text('<!doctype html><title>prototype</title>', encoding='utf-8')
    ok(STATE_TOOL, 'confirm-concept', downgraded, '--quote', CONCEPT_LINE, '--structure-directions', 2)
    ok(STATE_TOOL, 'confirm-structure', downgraded, '--quote', STRUCTURE_LINE,
       '--prototype', downgraded / 'prototype.html')
    dropped = ok(STATE_TOOL, 'confirm-concept', downgraded, '--quote', CONCEPT_LINE, '--no-visual')
    assert dropped['voided_decisions'] == ['structure'], 'dropping the visual step must void the structure choice'
    assert json.loads((downgraded / '.site' / 'state.json').read_text(encoding='utf-8'))[
        'structure_confirmed'] is False
    assert [row['label'] for row in ok(STATE_TOOL, 'show', downgraded)['consent_replay']] == ['首版方案确认']

    # 10h. One sentence split across two gates is still one expression of consent.
    split = temp / 'split'
    ok(SITE_TOOL, 'init', split, '--template', 'static', '--title', '拆句回归')
    (split / 'prototype.html').write_text('<!doctype html><title>prototype</title>', encoding='utf-8')
    ok(STATE_TOOL, 'confirm-concept', split, '--quote', CONCEPT_LINE, '--structure-directions', 1)
    ok(STATE_TOOL, 'confirm-visual', split, '--quote', VISUAL_LINE, '--prototype', split / 'prototype.html')
    assert 'overlaps the sentence' in refused(
        STATE_TOOL, 'authorize-build', split, '--quote', VISUAL_LINE + '那就开始做吧。')

    # 10i. Only an explicit false declares "this scope needs no visual step".
    hand = temp / 'hand-written'
    (hand / '.site').mkdir(parents=True)
    (hand / '.site' / 'state.json').write_text(json.dumps({
        'schema_version': 2, 'project_id': 'hand-written', 'revision': 1, 'stage': 'visual_review',
        'concept_confirmed': True, 'structure_required': False, 'structure_confirmed': False,
        'visual_required': None, 'visual_confirmed': False, 'development_authorized': False,
    }), encoding='utf-8')
    refused(STATE_TOOL, 'authorize-build', hand, '--quote', AUTHORIZE_LINE)

    # 11. The three independent fingerprint() implementations must agree on a hard tree.
    # They claim to be byte-identical; nothing else forces that, and a silent drift here
    # would void every frozen acceptance fingerprint while every other test stayed green.
    hard = temp / 'hard-tree'
    (hard / '.site' / 'checks').mkdir(parents=True)
    (hard / '.site' / 'design').mkdir()
    (hard / 'assets' / 'deep').mkdir(parents=True)
    (hard / '.hidden-dir').mkdir(parents=True)
    (hard / 'index.html').write_text('<!doctype html><title>hard</title>', encoding='utf-8')
    (hard / 'assets' / 'deep' / 'app.js').write_text('console.log(1)', encoding='utf-8')
    (hard / '.site' / 'brief.md').write_text('# 目标', encoding='utf-8')
    (hard / '.site' / 'implementation-plan.md').write_text('# 计划', encoding='utf-8')
    (hard / '.site' / 'design' / 'prototype.html').write_text('<title>direction a</title>', encoding='utf-8')
    (hard / '.site' / 'state.json').write_text(json.dumps({'schema_version': 2, 'project_id': 'hard'}))
    (hard / '.site' / 'lease.json').write_text('{}', encoding='utf-8')
    (hard / '.site' / 'checks' / 'c.json').write_text('{}', encoding='utf-8')
    (hard / '.hidden-dir' / 'ignored.txt').write_text('hidden', encoding='utf-8')
    (hard / '.DS_Store').write_text('junk', encoding='utf-8')
    # Symlinks are ignored by the walk: as a directory and as a file, including one that
    # points outside the tree, which must not be followed or hashed.
    outside = temp / 'outside.txt'
    outside.write_text('outside', encoding='utf-8')
    (hard / 'linked-dir').symlink_to(hard / 'assets')
    (hard / 'linked-file.js').symlink_to(outside)
    assert 'regular directory' in refused(
        CHECK_TOOL, 'static', hard, '--web-root', 'linked-dir'
    ), 'an explicit web root must not be accepted through a symlink'
    gates = ok(STATE_TOOL, 'show', hard)['fingerprint']
    statics = ok(CHECK_TOOL, 'static', hard)['fingerprint']
    inspected_hard = ok(SITE_TOOL, 'inspect', hard)['fingerprint']
    assert gates == statics == inspected_hard, (
        f'fingerprint implementations disagree: state={gates[:12]} check={statics[:12]} site={inspected_hard[:12]}'
    )
    (hard / '.site' / 'design' / 'prototype.html').write_text('<title>direction b</title>', encoding='utf-8')
    changed_gates = ok(STATE_TOOL, 'show', hard)['fingerprint']
    changed_statics = ok(CHECK_TOOL, 'static', hard)['fingerprint']
    changed_inspected = ok(SITE_TOOL, 'inspect', hard)['fingerprint']
    assert changed_gates == changed_statics == changed_inspected
    assert changed_gates != gates, 'changing .site/design must invalidate the frozen source fingerprint'
    PASSED += 1

    print(f'OK: {PASSED} gate assertions passed')


if __name__ == '__main__':
    main()
