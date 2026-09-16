#!/usr/bin/env python3
"""Small release regression for the visual-direction and confirmation gates."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PY = sys.executable
SITE_TOOL = REPO / 'site-builder' / 'scripts' / 'site.py'
STATE_TOOL = REPO / 'site-brief' / 'scripts' / 'state.py'
DESIGN_TOOL = REPO / 'site-design' / 'scripts' / 'design.py'


def run(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([PY, str(script), *(str(arg) for arg in args)], text=True, capture_output=True)


def ok(script: Path, *args: object) -> dict:
    result = run(script, *args)
    if result.returncode:
        raise AssertionError(f'{script.name} failed: {result.stderr.strip()}')
    return json.loads(result.stdout)


def refused(script: Path, *args: object) -> str:
    result = run(script, *args)
    if result.returncode != 2:
        raise AssertionError(f'{script.name} should refuse, exit={result.returncode}: {result.stderr}')
    return json.loads(result.stderr)['error']


def main() -> None:
    research = ok(DESIGN_TOOL, 'research', 'inventory desktop dashboard', '--design-system', '--project-name', 'Regression')
    for key in ('layout_motif', 'component_patterns', 'density', 'variation_axes', 'anti_skin_check'):
        assert key in research and research[key], f'research missing structural hint: {key}'
    assert 'data-matrix' in research['layout_motif']

    with tempfile.TemporaryDirectory(prefix='site-gate-') as folder:
        root = Path(folder).resolve() / 'project'
        ok(SITE_TOOL, 'init', root, '--template', 'static', '--title', '视觉门禁回归')
        prototype = root / 'web' / 'index.html'
        ok(STATE_TOOL, 'confirm-concept', root, '--quote', '第一版范围确认，继续做体验稿。',
           '--structure-directions', '1')

        missing_contract = refused(
            STATE_TOOL, 'confirm-visual', root, '--quote', '采用这个视觉。', '--prototype', prototype,
        )
        assert 'surface-brief.md' in missing_contract

        contract = root / '.site' / 'design' / 'surface-brief.md'
        contract.parent.mkdir(parents=True)
        contract.write_text(
            '# Design contract\n\n'
            'ui-ux-pro-max: Query: inventory desktop dashboard | Style ID: data-matrix\n'
            '- **类别默认：** Hero + Features + CTA\n'
            '- **反默认原因：** 个人工具需要直接进入记账\n'
            '- **替代结构：** 记录流与对象详情并置\n'
            '- **交换检查结论：** 统一颜色和字体后，布局重心仍不同\n'
            '- **结构差异证据：** 主布局容器、核心组件形态、信息密度、首屏重心\n',
            encoding='utf-8',
        )
        contract.write_text(
            '# Design contract\n\n'
            'ui-ux-pro-max: Query: inventory desktop dashboard\n'
            '- **类别默认：** Hero + Features + CTA\n'
            '- **反默认原因：** 个人工具需要直接进入记账\n'
            '- **替代结构：** 记录流与对象详情并置\n'
            '- **交换检查结论：** 统一颜色和字体后，布局重心仍不同\n'
            '- **结构差异证据：** 主布局容器、核心组件形态、信息密度、首屏重心\n',
            encoding='utf-8',
        )
        message = refused(STATE_TOOL, 'confirm-visual', root, '--quote', '采用第二个视觉方案。', '--prototype', prototype)
        assert 'Style/Result ID' in message

        contract.write_text(
            '# Design contract\n\n'
            'ui-ux-pro-max: Query: inventory desktop dashboard | Style ID: data-matrix\n'
            '- **类别默认：** Hero + Features + CTA\n'
            '- **反默认原因：** 个人工具需要直接进入记账\n'
            '- **替代结构：** 记录流与对象详情并置\n'
            '- **交换检查结论：** 统一颜色和字体后，布局重心仍不同\n'
            '- **结构差异证据：** 主布局容器、核心组件形态、信息密度、首屏重心\n',
            encoding='utf-8',
        )
        visual = ok(STATE_TOOL, 'confirm-visual', root, '--quote', '采用第二个视觉方案。', '--prototype', prototype)
        assert visual['visual_confirmed'] is True
        assert visual['surface_brief_validated'] is True

        no_visual_root = Path(folder).resolve() / 'no-visual-project'
        ok(SITE_TOOL, 'init', no_visual_root, '--template', 'static', '--title', 'No visual')
        no_visual_prototype = no_visual_root / 'web' / 'index.html'
        ok(STATE_TOOL, 'confirm-concept', no_visual_root, '--quote', '先按现有系统实现。', '--no-visual')
        no_visual_message = refused(
            STATE_TOOL, 'confirm-visual', no_visual_root, '--quote', '还是采用这个视觉。',
            '--prototype', no_visual_prototype,
        )
        assert 'no-visual' in no_visual_message

    print('OK: visual-direction regression passed')


if __name__ == '__main__':
    main()
