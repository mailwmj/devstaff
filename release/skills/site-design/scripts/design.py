"""Research directions and compose portable design tokens. Python 3.9+, stdlib only."""
import argparse
import difflib
import fnmatch
import hashlib
import io
import json
import math
import os
import tarfile
from pathlib import Path, PurePath
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import unquote

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stdin, 'reconfigure'):
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')

GROUPS = {'palette': 'palettes', 'typography': 'typographies', 'density': 'densities',
          'shape': 'shapes', 'layout': 'layouts'}
INTELLIGENCE_VERSION = '2.13.0'
INTELLIGENCE_DOMAINS = (
    'style', 'color', 'chart', 'landing', 'product', 'ux',
    'typography', 'google-fonts', 'icons', 'gsap', 'react', 'web',
)
INTELLIGENCE_STACKS = (
    'react', 'nextjs', 'vue', 'svelte', 'astro', 'nuxtjs', 'nuxt-ui',
    'angular', 'laravel', 'swiftui', 'react-native', 'flutter',
    'jetpack-compose', 'html-tailwind', 'shadcn', 'threejs', 'javafx',
    'wpf', 'winui', 'avalonia', 'uno', 'uwp',
)


def resources():
    here = Path(__file__).resolve().parent
    return here / 'design' if (here / 'design/tokens.json').exists() else here.parent / 'assets/design'


def intelligence_root():
    return Path(__file__).resolve().parent.parent / 'intelligence'


def intelligence_environment():
    environment = os.environ.copy()
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['PYTHONUTF8'] = '1'
    environment['PYTHONIOENCODING'] = 'utf-8'
    return environment


def intelligence_source():
    return {
        'name': 'design-intelligence',
        'version': INTELLIGENCE_VERSION,
        'bundled': True,
        'license': 'MIT',
    }


def intelligence_catalog():
    """Expose the bundled search surface without making agents inspect data files."""
    summary_path = intelligence_root() / 'data' / 'catalog-summary.json'
    if not summary_path.is_file():
        raise ValueError('Bundled design intelligence catalog is missing')
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    stack_files = tuple(sorted(path.stem for path in (intelligence_root() / 'data' / 'stacks').glob('*.csv')))
    if set(stack_files) != set(INTELLIGENCE_STACKS):
        raise ValueError('Bundled design intelligence stack catalog is inconsistent')
    if summary.get('counts', {}).get('stacks') != len(INTELLIGENCE_STACKS):
        raise ValueError('Bundled design intelligence stack count is inconsistent')
    return {
        'source': intelligence_source(),
        'domains': list(INTELLIGENCE_DOMAINS),
        'stacks': list(INTELLIGENCE_STACKS),
        'counts': summary.get('counts', {}),
        'verified_at': summary.get('verifiedAt'),
        'query_contract': {
            'one_dominant_intent': True,
            'recommended_terms': '2-5',
            'retry_limit': 1,
            'fallback': 'record no_verified_match and apply project rules',
            'decision_target': '.site/design/surface-brief.md#设计方法来源',
        },
    }


def _result_identity(result):
    """Return one stable candidate identity from any upstream result shape."""
    if not isinstance(result, dict):
        return None
    design_system = result.get('design_system')
    if isinstance(design_system, dict):
        identities = design_system.get('source_identities')
        if isinstance(identities, dict):
            parts = [f'{key}={value}' for key, value in identities.items() if value]
            if parts:
                return 'design-system:' + '|'.join(parts)
        style = design_system.get('style')
        if isinstance(style, dict) and style.get('id'):
            return 'style:' + str(style['id'])

    rows = result.get('results')
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return None
    row = rows[0]
    identity_fields = (
        'Style ID', 'Pattern ID', 'Product Type', 'Font Pairing Name', 'Family',
        'Data Type', 'Issue', 'Icon Name', 'Guideline', 'Name', 'Title',
        'Category', 'Rule',
    )
    for field in identity_fields:
        if row.get(field):
            return f'{field}:{row[field]}'
    for field, value in row.items():
        if value not in (None, ''):
            return f'{field}:{value}'
    return None


def _retrieval_record(args, result):
    design_system = result.get('design_system') if isinstance(result, dict) else None
    if isinstance(design_system, dict) and design_system:
        count = 1
    elif isinstance(result, dict) and isinstance(result.get('results'), list):
        count = len(result['results'])
    else:
        count = 0
    route = 'design-system' if args.design_system else (
        f'stack:{args.stack}' if args.stack else f'domain:{args.domain}')
    top_result_id = _result_identity(result) if count else None
    status = 'verified_match' if count and top_result_id else 'no_verified_match'
    return {
        'status': status,
        'route': route,
        'result_count': count,
        'top_result_id': top_result_id,
        'next_action': (
            'check_project_fit_before_selecting'
            if status == 'verified_match'
            else 'retry_once_then_record_fallback'
        ),
    }


def _density_hint(design_system):
    """Return a layout density hint without treating a catalog style as a decision."""
    dials = design_system.get('dials') or {}
    label = dials.get('density_label')
    if label:
        return str(label)
    text = ' '.join(
        str(design_system.get(key) or '')
        for key in ('category', 'style', 'pattern', 'typography', 'key_effects')
    ).lower()
    if any(word in text for word in ('dense', 'compact', 'dashboard', 'analytics', 'data')):
        return 'compact'
    if any(word in text for word in ('spacious', 'airy', 'editorial', 'luxury')):
        return 'spacious'
    return 'balanced'


def _layout_guidance(design_system):
    """Translate search metadata into implementable, reviewable shape hints.

    These hints widen the candidate pool; they are not a substitute for the
    project-specific mother theme, content facts, or user confirmation.
    """
    category = str(design_system.get('category') or '').lower()
    pattern = design_system.get('pattern') or {}
    sections = str(pattern.get('sections') or '')
    if any(word in category for word in ('inventory', 'dashboard', 'analytics', 'admin', 'operations')):
        motif = 'data-matrix-with-summary-ribbon'
        components = ['summary-ribbon', 'filter-toolbar', 'data-table-or-list', 'inline-status-and-actions']
    elif any(word in category for word in ('ecommerce', 'commerce', 'shopping', 'retail')):
        motif = 'filter-rail-with-product-grid'
        components = ['filter-rail', 'product-grid', 'comparison-or-quantity-control', 'persistent-cart-action']
    elif any(word in category for word in ('portfolio', 'gallery', 'editorial', 'publication')):
        motif = 'editorial-grid-with-featured-detail'
        components = ['featured-item', 'asymmetric-grid', 'metadata-rail', 'related-items']
    elif any(word in category for word in ('education', 'course', 'learning')):
        motif = 'lesson-rail-with-progress-detail'
        components = ['current-task-panel', 'progress-rail', 'feedback-state', 'next-action']
    else:
        motif = 'content-led-section-flow'
        components = [part.strip() for part in sections.split('>') if part.strip()][:4]
        if not components:
            components = ['primary-content', 'supporting-detail', 'next-action']
    return {
        'layout_motif': motif,
        'component_patterns': components,
        'density': _density_hint(design_system),
        'variation_axes': ['layout topology', 'core component shape', 'information density', 'visual focal point'],
        'anti_skin_check': 'After swapping colors and fonts, these structural axes must still differ between candidates.',
    }


_ICON_VENDOR_FIELDS = ('Library', 'Import Code')
# Every curated row leads its Usage with library-specific JSX or library-choice
# advice, then ends with the same library-agnostic accessibility guidance. Only
# that guidance may steer an undecided project, so Usage keeps it and nothing
# else; a row without the marker loses the field rather than leak a vendor.
_ICON_USAGE_MARKER = 'Context is chosen by use:'

# Routes whose payload carries ready-to-paste artifacts (imports, font URLs,
# palettes, preset names) that an unwarned reader could take for project law.
_RETRIEVAL_NOTES = {
    'icons': '默认 Lucide：这里只给图标语义、命名与场景无障碍要求，不要照搬任何库、'
             'import 代码或 Vendor JSX。用户或现有工程已明确指定其他图标体系时，'
             '以该指定为准并写入合同 icon_system。',
    'typography': '字体角色与配对只是候选，返回的 Google Fonts URL 与 CSS Import 不是项目标准；'
                  '是否加载网络字体由项目事实与设计需要决定，加载时必须配系统栈回退，'
                  '中文字体结论与加载纪律以 chinese-typography.md 为准。',
    'google-fonts': '条目只证明候选存在；许可、中文覆盖、加载与离线策略需单独核对，'
                    '已有字体系统优先继承。',
}
_DESIGN_SYSTEM_NOTE = (
    '返回的色板、字体、pattern 与技术栈建议都是候选，不是项目标准：'
    '配色 / 字体 / 密度 / 形状以 design-tokens.md 为准，落地页版式以 landing-page.md 为准，'
    '并必须用项目事实写出 fit_basis。'
)


def _strip_icon_vendor(result):
    """Withhold the icon snapshot's vendor identity, snippets and vendor JSX.

    The bundled snapshot is Phosphor-based while this pack defaults to Lucide.
    Only the icon's semantic role and name may steer the default, so the
    snapshot cannot quietly decide the icon library for an undecided project.
    The data file itself stays a byte-faithful upstream snapshot.
    """
    if not isinstance(result, dict) or result.get('domain') != 'icons':
        return result
    rows = result.get('results')
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in _ICON_VENDOR_FIELDS:
            row.pop(field, None)
        usage = row.get('Usage')
        if isinstance(usage, str):
            index = usage.find(_ICON_USAGE_MARKER)
            if index >= 0:
                row['Usage'] = usage[index:]
            else:
                row.pop('Usage', None)
    return result


def _apply_retrieval_note(result):
    """State how to treat a payload whose values could pass for project law."""
    if not isinstance(result, dict):
        return result
    if isinstance(result.get('design_system'), dict):
        result['retrieval_note'] = _DESIGN_SYSTEM_NOTE
    else:
        note = _RETRIEVAL_NOTES.get(result.get('domain'))
        if note:
            result['retrieval_note'] = note
    return result


def research(args):
    """Run the bundled UI/UX search behind this skill's stable interface."""
    root = intelligence_root()
    script = root / 'scripts' / 'search.py'
    if not script.is_file():
        raise ValueError('Bundled design intelligence is missing')

    command = [sys.executable, str(script), args.query, '--json']
    if args.design_system:
        command.append('--design-system')
        if args.project_name:
            command.extend(('--project-name', args.project_name))
        for name in ('variance', 'motion', 'density'):
            value = getattr(args, name)
            if value is not None:
                command.extend(('--' + name, str(value)))
    elif args.stack:
        command.extend(('--stack', args.stack))
        command.extend(('--max-results', str(args.max_results)))
    else:
        if args.domain:
            command.extend(('--domain', args.domain))
        command.extend(('--max-results', str(args.max_results)))

    completed = subprocess.run(
        command, text=True, capture_output=True, env=intelligence_environment(),
        encoding='utf-8', errors='replace')
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or 'unknown error'
        raise ValueError('Bundled design intelligence failed: ' + detail)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError('Bundled design intelligence returned invalid JSON') from error
    result = _apply_retrieval_note(_strip_icon_vendor(result))

    mode = 'design-system' if args.design_system else ('stack' if args.stack else 'domain')
    retrieval = _retrieval_record(args, result)
    payload = {
        'source': intelligence_source(),
        'mode': mode,
        'query': args.query,
        'retrieval': retrieval,
        'decision_record': {
            'query': args.query,
            'route': retrieval['route'],
            'candidate_id': retrieval['top_result_id'],
            'selected': None,
            'fit_basis': [],
            'rejected_reason': None,
            'contract_target': '.site/design/surface-brief.md#设计方法来源',
        },
        'result': result,
    }
    design_system = result.get('design_system') if isinstance(result, dict) else None
    if isinstance(design_system, dict):
        payload.update(_layout_guidance(design_system))
    else:
        payload.update({
            'layout_motif': None,
            'component_patterns': [],
            'density': 'unknown',
            'variation_axes': ['layout topology', 'core component shape', 'information density', 'visual focal point'],
            'anti_skin_check': 'No design-system result; derive structural differences from project evidence before presenting candidates.',
        })
    return payload


def validate_intelligence():
    root = intelligence_root()
    version = root / 'VERSION'
    license_path = root / 'LICENSE'
    validator = root / 'scripts' / 'validate_data.py'
    if not version.is_file() or version.read_text(encoding='utf-8').strip() != INTELLIGENCE_VERSION:
        raise ValueError('Bundled design intelligence version is missing or mismatched')
    if not license_path.is_file() or not validator.is_file():
        raise ValueError('Bundled design intelligence license or validator is missing')
    completed = subprocess.run(
        [sys.executable, str(validator)], text=True, capture_output=True,
        env=intelligence_environment(), encoding='utf-8', errors='replace')
    if completed.returncode:
        detail = completed.stdout.strip() or completed.stderr.strip() or 'unknown error'
        raise ValueError('Bundled design intelligence validation failed: ' + detail)
    return completed.stdout.strip()


def read_catalog(path=None):
    data = json.loads((path or resources() / 'tokens.json').read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported token catalog')
    return data


def contrast(a, b):
    def luminance(color):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError(f'Expected opaque hex color: {color}')
        values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return (linear[0] * .2126 + linear[1] * .7152) + linear[2] * .0722
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + .05) / (dark + .05)


def color_checks(tokens):
    pairs = [(fg, bg, 4.5) for fg in ('text', 'text-muted')
             for bg in ('canvas', 'surface', 'surface-raised')]
    pairs += [('on-accent', 'accent', 4.5), ('on-accent', 'accent-hover', 4.5),
              ('on-selection', 'selection', 4.5), ('accent', 'canvas', 4.5),
              ('accent', 'surface', 4.5)]
    pairs += [(state, state + '-surface', 4.5) for state in ('success', 'error', 'warning')]
    pairs += [(fg, bg, 3) for fg in ('border-control', 'focus') for bg in ('canvas', 'surface')]
    return [{'foreground': fg, 'background': bg, 'ratio': contrast(tokens[fg], tokens[bg]),
             'minimum': minimum, 'passed': contrast(tokens[fg], tokens[bg]) >= minimum}
            for fg, bg, minimum in pairs]


def px(value):
    match = re.fullmatch(r'([0-9.]+)px', value.strip())
    return float(match.group(1)) if match else None


# Craft floors mirrored in references/craft-review.md.  They guard the catalog's own
# defaults, not the project's final page: an established design system may
# override the heuristic values, but the catalog must never ship a broken one.
TYPOGRAPHY_FLOORS = {'text-reading': 16.0, 'text-body': 16.0, 'text-label': 14.0, 'text-caption': 12.0}
TYPOGRAPHY_LEADING_FLOOR = 1.7
FORBIDDEN_FONT_HINTS = ('Söhne', 'Soehne', 'Circular', 'Gotham', 'Helvetica Now', 'GT ', 'Larsseit')


def typography_checks(tokens):
    rows = []
    for key, floor in TYPOGRAPHY_FLOORS.items():
        size = px(str(tokens[key]))
        rows.append({'token': key, 'value': tokens[key], 'minimum': floor,
                     'passed': size is not None and size >= floor})
    leading = float(str(tokens['leading-reading']).strip())
    rows.append({'token': 'leading-reading', 'value': tokens['leading-reading'],
                 'minimum': TYPOGRAPHY_LEADING_FLOOR, 'passed': leading >= TYPOGRAPHY_LEADING_FLOOR})
    tracking = str(tokens['tracking-heading']).strip()
    negative = tracking.startswith('-') and not re.fullmatch(r'-0(\.0+)?(em|px|%)?', tracking)
    rows.append({'token': 'tracking-heading', 'value': tracking, 'minimum': '0 (CJK headings)',
                 'passed': not negative})
    fonts = ' '.join(str(tokens[key]) for key in ('font-ui', 'font-heading', 'font-reading'))
    licensed = [name for name in FORBIDDEN_FONT_HINTS if name in fonts]
    rows.append({'token': 'font-*', 'value': 'licensed font names', 'minimum': 'system or open fonts only',
                 'passed': not licensed})
    return rows


def unknown_choice(kind, value, valid):
    """Reject an unknown key by naming the keys that exist.

    `Unknown palette: cobal` cost the caller a whole round trip to learn what
    --palette accepts, and the answer is not in design-tokens.md. The caller is
    usually an agent that cannot guess `cobalt` from a typo, so the message
    carries the full vocabulary and the closest key.
    """
    options = [str(option) for option in valid]
    close = difflib.get_close_matches(str(value), options, n=1, cutoff=0.6)
    hint = f'; did you mean {close[0]}?' if close else ''
    return ValueError(f"Unknown {kind} {value!r}: valid keys are "
                      f"{', '.join(options)}{hint}")


def compose(data, recipe, **overrides):
    if recipe not in data['recipes']:
        raise unknown_choice('recipe', recipe, data['recipes'])
    chosen = data['recipes'][recipe]
    unknown = set(overrides) - set(GROUPS)
    if unknown:
        raise ValueError(f'Unknown override groups: {sorted(unknown)}; valid groups are '
                         f"{', '.join(GROUPS)}")
    selection = {key: overrides.get(key) or chosen[key] for key in GROUPS}
    tokens = dict(data['base'])
    for key, group in GROUPS.items():
        if selection[key] not in data[group]:
            raise unknown_choice(key, selection[key], data[group])
        tokens.update(data[group][selection[key]]['tokens'])
    results = color_checks(tokens)
    failed = [f"{r['foreground']}/{r['background']}={r['ratio']:.2f}" for r in results if not r['passed']]
    if failed:
        raise ValueError('Color pairs below catalog thresholds: ' + ', '.join(failed))
    typo = typography_checks(tokens)
    typo_failed = [f"{r['token']}={r['value']}" for r in typo if not r['passed']]
    if typo_failed:
        raise ValueError('Typography floors violated: ' + ', '.join(typo_failed))
    return {'catalog_version': data['version'], 'recipe': recipe, 'selection': selection,
            'tokens': tokens, 'color_checks': results, 'typography_checks': typo,
            'roles': data['typographies'][selection['typography']]['roles'],
            'layout_guidance': data['layouts'][selection['layout']]['guidance'],
            'limits': ['Opaque listed color pairs only; not full accessibility or visual acceptance.',
                       'Typography floors guard catalog defaults, not a rendered page.',
                       'Selection records tool configuration, not user approval.']}


def css_text(result):
    lines = ['/* Generated design tokens; scope or map to the existing design system as needed. */', ':root {']
    lines.extend(f'  --ds-{key}: {value};' for key, value in result['tokens'].items())
    return '\n'.join(lines + ['}', ''])


def intent_text(result):
    selection = ', '.join(f'{key}={value}' for key, value in result['selection'].items())
    evidence = result.get('direction_evidence') or {}
    if evidence.get('mode') == 'direction-gate':
        source = ('方向依据：本稿由项目合同 `'
                  + str(evidence.get('contract_sha256') or '')[:12] + '` 的方向闸门放行，'
                  '方向变化后必须重新生成。')
    else:
        source = ('方向依据：**无**。本稿以 `--standalone` 生成，未读取任何项目合同，'
                  '不得作为已确认方向使用。')
    return f'''# 项目设计意图

> 这是由 `{result['recipe']}` 生成的实现校准草稿。{source}它需要结合项目方向合同填写，不代表用户已确认设计方向。

## North Star
这套设计要让用户更容易：

## 适用页面
- 页面 / surface：
- 主任务：
- 用户路径：

## 当前校准
- recipe：`{result['recipe']}`
- 选择：`{selection}`
- 布局提示：{result['layout_guidance']}

数值请以同目录的 `tokens.css` 和 `selection.json` 为准，不要在本文件复制颜色、字号、间距或圆角值。

## 视觉角色
- 内容主角：
- 视觉世界或材料依据：
- 首屏命题：
- 主要强调方式：

## 规则与理由
- 规则：
  - 理由：
  - 适用：
  - 例外：

## 组件契约
- 组件：
  - 角色：
  - 状态：
  - 内容极限：
  - 响应行为：

## 参考与素材
- 来源：
- 确定性：`measured | derived | inferred`
- 继承：
- 禁止复制：
- 许可或 provenance：

## 验证证据
- 页面 / 状态 / 视口：
- 设计判断：
- 任务与状态：
- 机械检查：
- 截图或操作记录：

## 例外与演化
- 例外：
- 变更：
- 变更理由：
'''


def gallery_html(data, template, primitives):
    recipes = {key: {**value, **compose(data, key)} for key, value in data['recipes'].items()}
    payload = json.dumps(recipes, ensure_ascii=False).replace('<', '\\u003c')
    return template.replace('__PRIMITIVES__', primitives).replace('__RECIPES__', payload)


CATALOG_BLOCK = re.compile(
    r'(<script type="application/json" id="catalog">)(.*?)(</script>)', re.DOTALL)
STALE_CATALOG = 'Gallery catalog payload is stale'


def sync_gallery(data, path):
    """Re-inject the composed catalog into the existing gallery, in place.

    The gallery keeps its own markup and styles; only the embedded recipe
    payload is regenerated, so it cannot drift from tokens.json.
    """
    if not path.is_file():
        raise ValueError(f'Gallery not found: {path}')
    text = path.read_text(encoding='utf-8')
    if not CATALOG_BLOCK.search(text):
        raise ValueError('Gallery has no <script id="catalog"> block to update')
    recipes = {key: {**value, **compose(data, key)} for key, value in data['recipes'].items()}
    payload = json.dumps(recipes, ensure_ascii=False).replace('<', '\\u003c')
    updated = CATALOG_BLOCK.sub(lambda m: m.group(1) + payload + m.group(3), text, count=1)
    if updated == text:
        return False
    path.write_text(updated, encoding='utf-8')
    return True


def _payload_equal(a, b):
    """Recursively compare parsed payloads, tolerating float precision differences across Python versions."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_payload_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_payload_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-7)
    return a == b


def gallery_catalog_drift(data=None):
    """Return a reason string when gallery.html disagrees with tokens.json.

    ``None`` means in sync (or no gallery to check). Shared by ``validate``,
    which owns --auto-sync, and ``check-contract``, which reports the drift at
    the moment the tool is used.
    """
    gallery = resources() / 'gallery.html'
    if not gallery.is_file():
        return None
    try:
        data = read_catalog() if data is None else data
        text = gallery.read_text(encoding='utf-8')
    except (OSError, ValueError):
        return None
    match = CATALOG_BLOCK.search(text)
    if not match:
        return 'Gallery has no <script id="catalog"> block.'
    expected = json.dumps(
        {key: {**value, **compose(data, key)} for key, value in data['recipes'].items()},
        ensure_ascii=False).replace('<', '\\u003c')
    if match.group(2) == expected:
        return None
    try:
        if _payload_equal(json.loads(match.group(2)), json.loads(expected)):
            return None
    except Exception:
        pass
    return STALE_CATALOG


# --- design contract check ------------------------------------------------
# The contract is the project's copy of surface-brief.md. A fixed
# ```site-contract``` JSON fenced block indexes the IDs defined in the body
# (BR/IC/PG/SC/RP/CP/AS/VA); it never copies the prose. check-contract reads
# that index, resolves references against the body, and reports whether the
# contract is ready for the requested phase. state.py start validates the
# SHA-256 and phase of a prebuild report before entering building.

CONTRACT_REL_PATH = '.site/design/surface-brief.md'
CONTRACT_BLOCK_RE = re.compile(r'```(?:site-contract|v3-contract)\n(.*?)\n```', re.DOTALL)
ID_TOKEN_RE = re.compile(r'`([A-Z]{2}-\d{2})`')
CONTRACT_LIST_FIELDS = (
    'scope_refs', 'required_constraints', 'pages', 'sections', 'responsive',
    'components', 'assets', 'copy', 'acceptance', 'unresolved_confirm',
    'blocking_missing_assets', 'intentional_exceptions',
)
# Project facts the contract must state. They are the basis every derived
# judgment cites, so they are checked for presence, not for citation.
PROJECT_FACT_LABELS = ('使用者', '主任务', '业务对象', '真实内容')
# Derived design judgments. Each must be filled AND cite at least one project
# fact ID declared in the body. This measures grounding. The earlier check
# compared the value against the template string, which measured wording
# deviation instead: it passed on a synonym and failed on faithful reuse.
DESIGN_JUDGMENT_ASPECTS = (
    ('anti_default', ('反默认原因',)),
    ('visual_motif', ('设计主线', '母题')),
    ('composition', ('构图命题',)),
    ('detail_signature', ('细节签名',)),
)
# ID namespaces that count as a citable project fact. VA-* is deliberately
# absent: acceptance criteria are the contract's output, not its evidence.
EVIDENCE_ID_PREFIXES = ('BR', 'IC', 'PG', 'SC', 'RP', 'CP', 'AS', 'TX')
VAGUE_VA_TERMS = ('高级', '现代', '像参考', '时尚', '优雅', '大气', '精致')
CONTRACT_PHASES = ('direction', 'prebuild', 'precheck')


def contract_path(root):
    root_path = Path(root)
    if root_path.is_dir():
        for child in root_path.iterdir():
            if child.is_dir() and child.name.lower() in ('.site', '.v3'):
                candidate = child / 'design' / 'surface-brief.md'
                if candidate.is_file():
                    return candidate
    for rel in (CONTRACT_REL_PATH, '.SITE/design/surface-brief.md', '.v3/design/surface-brief.md'):
        candidate = root_path / rel
        if candidate.is_file():
            return candidate
    return root_path / CONTRACT_REL_PATH


def _read_contract_text(root):
    path = contract_path(root)
    if not path.is_file():
        raise ValueError(f'contract not found at {CONTRACT_REL_PATH}')
    return path.read_text(encoding='utf-8')


def _strip_contract_block(text):
    """Body text with the contract fenced block removed."""
    return CONTRACT_BLOCK_RE.sub('', text)


def _parse_contract_block(text):
    match = CONTRACT_BLOCK_RE.search(text)
    if not match:
        raise ValueError('contract block is missing')
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise ValueError(f'contract block is not valid JSON: {error}') from error
    if not isinstance(data, dict):
        raise ValueError('contract block must be a JSON object')
    return data


def _contract_lists(data):
    result = {}
    for key in CONTRACT_LIST_FIELDS:
        value = data.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f'contract field {key} must be a list')
        result[key] = [str(item) for item in value]
    return result


def _defined_ids(body):
    """Every concrete backtipped ID (BR-01, PG-01, ...) declared in the body."""
    return set(ID_TOKEN_RE.findall(body))


def _bullet_value(text, label):
    """Text following '- **LABEL：**' on a line, stripped. '' if absent."""
    pattern = re.compile(r'- \*\*' + re.escape(label) + r'[：:]\*\*\s*(.*)')
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if match:
            return match.group(1).strip()
    return ''


def _split_row(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def _table(body, *header_markers):
    """First markdown table whose header contains every marker; (header, rows)."""
    lines = body.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip().startswith('|') and index + 1 < len(lines):
            separator = lines[index + 1].strip()
            if separator.startswith('|') and set(separator) <= set('|:- '):
                header = _split_row(line)
                if all(any(marker in cell for cell in header) for marker in header_markers):
                    index += 2
                    rows = []
                    while index < len(lines) and lines[index].strip().startswith('|'):
                        rows.append(_split_row(lines[index]))
                        index += 1
                    return header, rows
        index += 1
    return [], []


def _column(header, *markers):
    for position, cell in enumerate(header):
        if any(marker in cell for marker in markers):
            return position
    return None


def _scope_targets(body):
    """Map each BR id in the 首版承诺 table to its 交接目标 ID cell text."""
    header, rows = _table(body, '来源引用', '交接目标')
    src = _column(header, '来源引用')
    target = _column(header, '交接目标')
    if src is None or target is None:
        return {}
    mapping = {}
    for row in rows:
        if src < len(row):
            cell = row[target] if target < len(row) else ''
            for identity in ID_TOKEN_RE.findall(row[src]):
                mapping[identity] = cell
    return mapping


def _constraint_impacts(body):
    """Map each IC id in the 任务交互合同 table to its 对结构/状态的影响 cell."""
    header, rows = _table(body, '约束', '对结构')
    identifier = _column(header, 'ID')
    impact = _column(header, '对结构', '状态')
    if identifier is None or impact is None:
        return {}
    mapping = {}
    for row in rows:
        if identifier < len(row):
            cell = row[impact] if impact < len(row) else ''
            for identity in ID_TOKEN_RE.findall(row[identifier]):
                mapping[identity] = cell
    return mapping


def _va_row(body, va):
    """Return (observable, axis) cells for a VA id, or (None, None) if absent."""
    header, rows = _table(body, '可观察标准', '检查轴')
    identifier = _column(header, 'ID')
    observable = _column(header, '可观察标准')
    axis = _column(header, '检查轴')
    if observable is None or axis is None:
        return None, None
    if identifier is None:
        identifier = 0
    for row in rows:
        if identifier < len(row) and va in ID_TOKEN_RE.findall(row[identifier]):
            obs = row[observable] if observable < len(row) else ''
            ax = row[axis] if axis < len(row) else ''
            return obs, ax
    return None, None


def _declared_facts(lists):
    """Project facts the contract structurally declares, namely its JSON index.

    Deliberately *not* every backticked ID in the body: a citation written
    into a bullet would then declare its own evidence and the grounding check
    would pass on any invented ID. ``broken_reference`` already proves the
    index is a subset of the body, so using the index is the stricter set.
    """
    declared = set()
    for values in lists.values():
        declared.update(values)
    return declared


def _cited_fact_ids(value, declared):
    """Project-fact IDs cited in a field value and declared by the contract."""
    return sorted({identity for identity in ID_TOKEN_RE.findall(value)
                   if identity.split('-')[0] in EVIDENCE_ID_PREFIXES
                   and identity in declared})


def _design_judgment_gaps(body, declared):
    """Return ``(missing, uncited)`` aspects of the derived design judgments.

    ``missing`` means the field is blank. ``uncited`` means the field is
    filled but cites no project fact the contract declares, so the judgment
    cannot be traced to anything specific to this product. Judgments grounded
    in the project are what makes a direction falsifiable: delete the cited
    facts and the claim should stop holding.
    """
    missing, uncited = [], []
    for aspect, labels in DESIGN_JUDGMENT_ASPECTS:
        value = ''
        for label in labels:
            value = _bullet_value(body, label)
            if value:
                break
        if not value:
            missing.append(aspect)
        elif not _cited_fact_ids(value, declared):
            uncited.append(aspect)
    return missing, uncited


def _design_judgment_blockers(body, lists):
    """Blockers for the derived design judgments, grounded in project facts.

    Shared by the prebuild phase and the token gate so the two cannot drift.
    """
    blockers = []
    for label in PROJECT_FACT_LABELS:
        if not _bullet_value(body, label):
            blockers.append({'code': 'missing_design_judgment',
                             'aspect': 'project_facts', 'detail': label})
    missing, uncited = _design_judgment_gaps(body, _declared_facts(lists))
    for aspect in missing:
        blockers.append({'code': 'missing_design_judgment', 'aspect': aspect})
    for aspect in uncited:
        blockers.append({
            'code': 'uncited_design_judgment', 'aspect': aspect,
            'detail': '需引用至少一条合同索引已声明、且正文已定义的项目事实（'
                      + ' / '.join(prefix + '-*' for prefix in EVIDENCE_ID_PREFIXES)
                      + '）；VA-* 是验收输出，不能作为依据'})
    return blockers


def _contract_report(root, phase, sha, passed, blockers, warnings):
    return {
        'project_root': str(root),
        'phase': phase,
        'contract_path': CONTRACT_REL_PATH,
        'contract_sha256': sha,
        'passed': passed,
        'blockers': blockers,
        'warnings': warnings,
        'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }


def check_contract(root, phase):
    """Check the project's design contract and return a machine-readable report.

    Only applicable fields are checked: empty lists mean a class of object is
    not used by the project, not that something is missing. Determined problems
    are blockers; package-health drift is a warning. The report's SHA-256 is
    computed over the whole contract file, so any edit invalidates a prior
    report.
    """
    if phase not in CONTRACT_PHASES:
        raise ValueError('phase must be one of: ' + ', '.join(CONTRACT_PHASES))
    root = Path(root).resolve()
    blockers = []
    warnings = []

    try:
        contract_text = _read_contract_text(root)
    except ValueError as error:
        return _contract_report(root, phase, '', False,
                                [{'code': 'missing_contract', 'detail': str(error)}], warnings)

    sha = hashlib.sha256(contract_text.encode('utf-8')).hexdigest()
    body = _strip_contract_block(contract_text)

    try:
        data = _parse_contract_block(contract_text)
        lists = _contract_lists(data)
    except ValueError as error:
        return _contract_report(root, phase, sha, False,
                                [{'code': 'invalid_contract', 'detail': str(error)}], warnings)

    defined = _defined_ids(body)
    work_type = str(data.get('work_type') or '').strip()
    structure_mode = str(data.get('structure_mode') or '').strip()

    # Broken references: IDs indexed by the contract but not declared in the body.
    if phase == 'direction':
        ref_fields = ('scope_refs',)
    else:
        ref_fields = ('scope_refs', 'required_constraints', 'pages', 'sections',
                      'responsive', 'components', 'assets', 'copy', 'acceptance')
    for field in ref_fields:
        for reference in lists.get(field, []):
            if reference not in defined:
                blockers.append(
                    {'code': 'broken_reference', 'field': field, 'ref': reference})

    if phase in ('direction', 'prebuild'):
        if not work_type:
            blockers.append({'code': 'missing_work_type'})
        if structure_mode not in ('single', 'choice'):
            blockers.append({'code': 'missing_structure_mode'})

    if phase in ('prebuild', 'precheck'):
        if lists['unresolved_confirm']:
            blockers.append({'code': 'unresolved_confirm',
                              'items': list(lists['unresolved_confirm'])})
        if lists['blocking_missing_assets']:
            blockers.append({'code': 'blocking_missing_asset',
                              'items': list(lists['blocking_missing_assets'])})
        for va in lists['acceptance']:
            observable, axis = _va_row(body, va)
            if observable is None:
                continue  # broken_reference already reported the missing VA
            if not observable.strip():
                blockers.append({'code': 'non_executable_va', 'ref': va,
                                 'detail': 'observable standard is empty'})
            elif not axis.strip():
                blockers.append({'code': 'non_executable_va', 'ref': va,
                                 'detail': 'check axis is empty'})
            else:
                vague = [term for term in VAGUE_VA_TERMS if term in observable]
                if vague:
                    # VA-* is the ground truth site-check verifies against. A
                    # standard nobody can decide makes every downstream browser
                    # check vacuous, so its downstream leverage is unbounded.
                    # Warn while the direction is still forming; block once
                    # implementation is about to start.
                    entry = {
                        'code': 'vague_va_standard', 'ref': va, 'terms': vague,
                        'detail': '无法判定的验收用词；改写为可在真实页面上取证的断言',
                    }
                    (blockers if phase == 'precheck' else warnings).append(entry)

    if phase == 'prebuild':
        scope_targets = _scope_targets(body)
        for reference in lists['scope_refs']:
            if reference in scope_targets and not scope_targets[reference].strip():
                blockers.append({'code': 'scope_ref_without_target', 'ref': reference})
        impacts = _constraint_impacts(body)
        for reference in lists['required_constraints']:
            if reference in impacts and not impacts[reference].strip():
                blockers.append({'code': 'required_constraint_without_target',
                                 'ref': reference})
        blockers.extend(_design_judgment_blockers(body, lists))

    # Package health: gallery.html embeds a copy of the composed catalog so it
    # can be opened straight from disk, so the two can drift. Surfacing it here
    # checks the invariant at the moment the tool is actually used rather than
    # only when someone remembers to run `validate`.
    drift = gallery_catalog_drift()
    if drift:
        warnings.append({'code': 'stale_gallery_catalog', 'detail': drift})

    return _contract_report(root, phase, sha, not blockers, blockers, warnings)


# --- token-selection gate ---------------------------------------------------
# `build` emits a ready-to-use tokens.css, which made the recipe catalog the one
# artifact reachable with no evidence at all -- the exact inverse of
# design-context.md, where gallery and 配方 sit at the lowest conflict priority.
# The gate composes rules that already exist rather than adding a consistency
# rule of its own: the direction-phase contract check, plus the design
# judgments design-tokens.md demands before token selection. It deliberately
# does not reuse the prebuild phase, because prebuild also demands scope
# targets, constraint impacts and executable VA rows that are still being
# written when a direction is being calibrated.


def direction_gate(root):
    """Report whether token selection is allowed for this project.

    ``passed`` is False while the contract is missing, unreadable, or does not
    yet state the derived design judgments (设计主线 / 反默认原因 / 构图命题 /
    细节签名) with citations to project facts the contract itself declares.
    The report carries the contract SHA-256 so a selection can be tied to the
    revision it was calibrated against, the same way state.py ties a build to
    a prebuild report.
    """
    report = dict(check_contract(root, 'direction'))
    if report['blockers']:
        return {**report, 'gate': 'direction'}
    text = _read_contract_text(Path(root).resolve())
    blockers = _design_judgment_blockers(
        _strip_contract_block(text), _contract_lists(_parse_contract_block(text)))
    return {**report, 'gate': 'direction', 'blockers': blockers,
            'passed': not blockers}


# --- UI lint (stage 3) ------------------------------------------------------
# lint-ui reads the project contract (declared icon system, emoji/unicode
# exceptions, excluded capabilities, visual-candidate evidence) and statically
# scans the project's UI source for deterministic anti-patterns. It is a
# read-only, stdlib-only check: it never starts a browser. Everything it
# reports as a blocker is a fact it can decide from the source text; aesthetic
# judgments are left to craft-review.md. Output is machine-readable JSON. Real
# user content, test fixtures, Markdown and data files are excluded from the
# scan; contract ``intentional_exceptions`` that look like paths or globs
# exempt matching files.

LINT_UI_EXTENSIONS = ('.html', '.htm', '.css', '.js', '.mjs', '.cjs',
                      '.jsx', '.ts', '.tsx', '.vue', '.svelte', '.astro')
LINT_IGNORE_DIRS = {'.site', '.SITE', '.v3', '.git', 'node_modules', '__pycache__', '.DS_Store',
                    'dist', 'build', '.next', '.nuxt', '.svelte-kit',
                    '.output', 'coverage', '.turbo', '.vercel', '.astro',
                    'prototypes', 'prototype', 'demos', 'demo', 'mockups',
                    'playground', 'scratch', 'experiments'}
LINT_FIXTURE_DIR_PARTS = {'tests', 'test', '__tests__', '__mocks__',
                          'fixtures', 'e2e', 'storybook', 'stories',
                          'snapshots', '__snapshots__'}
LINT_FIXTURE_NAME_RE = re.compile(r'(\.test\.|\.spec\.|\.stories\.|\.snap\.)',
                                  re.IGNORECASE)

# Unicode blocks of pictographs / symbols that are commonly pressed into
# service as icons. CJK and ordinary punctuation are intentionally absent.
_SYMBOL_RANGES = (
    (0x2190, 0x21FF), (0x2460, 0x24FF), (0x2500, 0x257F), (0x2580, 0x259F),
    (0x25A0, 0x25FF), (0x2600, 0x26FF), (0x2700, 0x27BF), (0x27C0, 0x27EF),
    (0x27F0, 0x27FF), (0x2B00, 0x2BFF), (0x1F1E6, 0x1F1FF), (0x1F300, 0x1F5FF),
    (0x1F600, 0x1F64F), (0x1F680, 0x1F6FF), (0x1F700, 0x1F77F),
    (0x1F780, 0x1F7FF), (0x1F800, 0x1F8FF), (0x1F900, 0x1F9FF),
    (0x1FA00, 0x1FAFF), (0x1FB00, 0x1FBFF),
)
_SYMBOL_CLASS = ''.join(f'{chr(lo)}-{chr(hi)}' for lo, hi in _SYMBOL_RANGES)
_SYMBOL_RE = re.compile('[' + _SYMBOL_CLASS + ']')
_STAR_RUN_RE = re.compile('[★⭐]{3,}')
# A symbol that is the sole visible content between two tags (``>SYM<``) is the
# signature of an icon, a status glyph or a pictograph, not prose. Script and
# style bodies are stripped first so symbols inside code never trip it.
_ICON_SOLO_RE = re.compile(r'>\s*([' + _SYMBOL_CLASS + r'])\s*<')
_SCRIPT_STYLE_RE = re.compile(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)>',
                              re.IGNORECASE | re.DOTALL)

_LOREM_RE = re.compile(r'lorem\s+ipsum|dolor\s+sit\s+amet', re.IGNORECASE)
_PLACEHOLDER_IMG_RE = re.compile(
    r'(?:via\.placeholder|placehold\.co|picsum\.photos|placekitten|dummyimage|'
    r'placeholder\.com|placebe|loremflickr)', re.IGNORECASE)
_LOGO_CTX_RE = re.compile(
    r'logo|brand|client|customer|testimonial|partner|客户|品牌|合作|评价|案例',
    re.IGNORECASE)

_IMPORT_RE = re.compile(r"""(?:from|require)\s*\(?\s*['"]([^'"]+)['"]""")
_LINK_SRC_RE = re.compile(r'<script\b[^>]*\bsrc=["\']([^"\']+)["\']',
                          re.IGNORECASE)
# A <link> tag is parsed as a whole so attribute order is not assumed:
# ``<link href="..." rel="stylesheet">`` is as valid as the reverse.
_LINK_TAG_RE = re.compile(r'<link\b[^>]*>', re.IGNORECASE)
_LINK_REL_RE = re.compile(r'\brel=["\']([^"\']*)["\']', re.IGNORECASE)
_LINK_HREF_RE = re.compile(r'\bhref=["\']([^"\']+)["\']', re.IGNORECASE)
# Only a stylesheet or preload href can reference an icon package. Scanning
# every <link href> once matched ``rel=canonical`` page metadata: a product id
# containing "feather" read as the Feather icon library.
_ICON_LINK_RELS = frozenset({'stylesheet', 'preload', 'modulepreload'})
_CLASS_VAL_RE = re.compile(r'(?:class|className)=["\']([^"\']*)["\']',
                           re.IGNORECASE)
_LABEL_TAG_RE = re.compile(
    r'<(?P<tag>h[1-6]|button|a|li|option|summary|label)\b[^>]*>'
    r'(?P<txt>.*?)</(?P=tag)>', re.IGNORECASE | re.DOTALL)
_ATTR_VAL_RE = re.compile(
    r'(?:class|className|id|alt|aria-label|placeholder|title|role)=["\']'
    r'([^"\']*)["\']', re.IGNORECASE)

# Pack default. An explicit user or existing-project choice overrides it, so
# this is the fallback for an undeclared contract, never a hard requirement.
LUCIDE_ICON_SYSTEM = 'lucide'

_ICON_SYSTEM_PACKAGES = (
    ('lucide', re.compile(r'lucide', re.IGNORECASE)),
    ('heroicons', re.compile(r'heroicons', re.IGNORECASE)),
    ('material-icons', re.compile(
        r'material[-_]icons|material[-_]symbols|@material/icons|@mui/icons',
        re.IGNORECASE)),
    ('font-awesome', re.compile(r'fortawesome|font[-_]?awesome', re.IGNORECASE)),
    ('phosphor', re.compile(r'phosphor', re.IGNORECASE)),
    ('tabler', re.compile(r'tabler', re.IGNORECASE)),
    ('bootstrap-icons', re.compile(r'bootstrap[-_]icons', re.IGNORECASE)),
    ('remixicon', re.compile(r'remixicon', re.IGNORECASE)),
    ('iconify', re.compile(r'@iconify|iconify', re.IGNORECASE)),
    ('feather', re.compile(r'feather', re.IGNORECASE)),
    ('ionicons', re.compile(r'ionicons|@ionic', re.IGNORECASE)),
    ('octicons', re.compile(r'octicons|@primer/octicons', re.IGNORECASE)),
)
_ICON_CLASS_PREFIXES = {
    'font-awesome': re.compile(r'^fa[bsrl]?(?:-|$)'),
    'bootstrap-icons': re.compile(r'^bi-'),
    'remixicon': re.compile(r'^ri-'),
    'css.gg': re.compile(r'^gg-'),
    'material-icons': re.compile(r'^(?:material-icons|material-symbols)(?:-|$)'),
    'iconify': re.compile(r'^iconify[:\[]'),
    'ionicons': re.compile(r'^ion-'),
}
# Markup signatures for systems that are not found via imports or class
# prefixes (e.g. lucide's ``data-lucide`` attribute or custom element).
_ICON_MARKUP_PATTERNS = {
    'lucide': re.compile(r'data-lucide\s*=|<lucide-', re.IGNORECASE),
    'ionicons': re.compile(r'<ion-icon\b', re.IGNORECASE),
    'eva-icons': re.compile(r'<eva-icon\b', re.IGNORECASE),
}

# --- page-integrity rules (contract-independent) ---------------------------
# These decide facts from the source text: a referenced file that is not on
# disk, two elements pinned to the same strip, all-caps leading that cannot
# clear the caps. Aesthetic judgment is not here -- see the note after
# ``_scan_file``. Only a dead local reference blocks: it is the failure that
# makes every other check vacuous, because a page whose stylesheet is missing
# renders unstyled and still passes the icon, proof and capability scans.
#
# CSS rules run only on files that carry CSS. Reading a JS/TSX file as if its
# object literals were declaration blocks would invent findings, and a warning
# that is often wrong trains agents to ignore warnings.

LINT_CSS_SUFFIXES = frozenset({'.css', '.html', '.htm', '.vue', '.svelte',
                               '.astro'})
# Runtime-motion rules need to see script, not just declarations. The two
# checks below are text patterns that read the same in an inline <script>, a
# component and a .js file, so they scan every script-capable suffix.
LINT_SCRIPT_SUFFIXES = frozenset({'.html', '.htm', '.js', '.mjs', '.cjs',
                                  '.jsx', '.ts', '.tsx', '.vue', '.svelte',
                                  '.astro'})
# A missing reference under a build-output directory may simply mean the build
# has not run yet; a missing reference anywhere else is a broken page.
LINT_BUILD_OUTPUT_DIRS = frozenset({'dist', 'build', 'out', '.next', '.nuxt',
                                    '.output', 'node_modules'})
# Opaque colour literals a file may carry outside its token block before the
# palette has stopped being a system somewhere. Translucent rgba()/hsla() are
# not counted: the craft rules require them inline for borders and shadows.
COLOR_LITERAL_LIMIT = 30

_ATTR_REF_RE = re.compile(
    r'\b(?:href|src|poster)\s*=\s*(?:["\']([^"\']+)["\']|([^\s>"\'`]+))',
    re.IGNORECASE)
# A reference only counts inside a tag or a CSS function. ``location.href =
# "signin.html"`` in a script and ``:src="path"`` in a JSX/Vue binding are
# not file references -- matching them made every router line a blocker.
_TAG_RE = re.compile(r'<[^<>]*>')
_BOUND_ATTR_RE = re.compile(r'(?<![:@.\w])\b(?:href|src|poster)\s*=')
_CSS_URL_RE = re.compile(r'(?<![-\w])url\(\s*["\']?([^"\')]+)["\']?\s*\)')
_CSS_IMPORT_RE = re.compile(
    r'@import\s+(?:url\(\s*)?["\']([^"\')]+)["\']', re.IGNORECASE)
# Scheme'd, protocol-relative and fragment-only refs are not local files, and
# a root-relative one has no serving root to resolve against.
_SKIP_REF_RE = re.compile(r'^(?:[a-z][a-z0-9+.\-]*:|//|#)', re.IGNORECASE)
_DYNAMIC_REF_RE = re.compile(r'[{}$<>()]')
_COMMENT_RE = re.compile(r'<!--.*?-->|/\*.*?\*/', re.DOTALL)
_CSS_BLOCK_RE = re.compile(r'([^{}]*)\{([^{}]*)\}')
_ROOT_SELECTOR_RE = re.compile(
    r'\s*(?:html|body)(?:\s*,\s*(?:html|body))*\s*$', re.IGNORECASE)
_CONTINUOUS_MOTION_RE = re.compile(
    r'requestAnimationFrame|\bgsap\b|ScrollTrigger|@keyframes'
    r'|animation-timeline\s*:', re.IGNORECASE)
_REDUCED_MOTION_RE = re.compile(r'prefers-reduced-motion', re.IGNORECASE)
_TRANSITION_ALL_RE = re.compile(r'transition\s*:\s*all\b|\btransition-all\b',
                                re.IGNORECASE)
# Animating a layout property invalidates style and layout every frame; the
# compositor never sees it. ``transition: all`` is caught above; these two
# patterns catch the explicit forms, in a transition list and in a keyframe.
_LAYOUT_PROP_RE = re.compile(
    r'(?<![-\w])(?:width|height|top|left|right|bottom'
    r'|margin(?:-(?:top|right|bottom|left))?'
    r'|padding(?:-(?:top|right|bottom|left))?'
    r'|font-size|line-height|border-width)(?![-\w])', re.IGNORECASE)
_TRANSITION_DECL_RE = re.compile(
    r'transition(?:-property)?\s*:\s*([^;}{]+)', re.IGNORECASE)
_DECL_START_RE = re.compile(r'(?:^|[;{])\s*([a-z-]+)\s*:', re.IGNORECASE)
# A keyframe step is the only place where these selectors are legal, so a block
# whose selector looks like one is a step and its body is pure declarations.
_KEYFRAME_STEP_RE = re.compile(r'^(?:from|to|\d+(?:\.\d+)?%)$', re.IGNORECASE)
# Reading geometry inside a per-frame loop forces a synchronous layout. The
# scan cannot prove the read sits in the same callback, so it reports a
# question (warning) rather than a verdict.
_FRAME_LOOP_RE = re.compile(r'requestAnimationFrame')
_LAYOUT_READ_RE = re.compile(
    r'getBoundingClientRect|getClientRects|offsetWidth|offsetHeight|offsetTop'
    r'|offsetLeft|clientWidth|clientHeight|scrollTop|scrollLeft'
    r'|getComputedStyle')
_GRADIENT_TEXT_RE = re.compile(r'background-clip\s*:\s*text', re.IGNORECASE)
_GRADIENT_RE = re.compile(r'(?:linear|radial|conic)-gradient', re.IGNORECASE)
_OPAQUE_COLOR_RE = re.compile(
    r'#[0-9a-fA-F]{6,8}\b|#[0-9a-fA-F]{3}\b|oklch\([^)]*\)')
_TOKEN_BLOCK_RE = re.compile(
    r'(?::root|\[data-theme[^\]]*\]|@theme)[^{]*\{[^{}]*\}', re.IGNORECASE)

# What the static scan cannot see. Published with every report so ``passed``
# never reads as "the design holds": the failures below need a rendered page,
# an eye or a browser.
LINT_NOT_COVERED = (
    '换行与触控：按钮在窄屏是否折行、点击热区够不够大，要渲染页面量',
    '对比度与真实色对：token 表通过不等于渲染后的相邻色对达标',
    '图表是否由数据驱动：柱高是否来自数值、轴标签是否齐全，要看渲染结果',
    '动效质量：静态扫描只查有没有降级开关，流畅与是否有意义看不出来',
    '素材内容：图片画的是什么、裁剪与 alt 是否恰当，文本判断不了',
    '生成式默认骨架：Hero+等权卡片这类形态由 craft-review.md 人工判',
    '根路径引用（/assets/x.png）：没有服务根，静态检查判断不了',
)


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _bullet_after(text, prefix):
    """Text after '- **PREFIX…:**', tolerating a trailing parenthetical."""
    pattern = re.compile(r'- \*\*' + re.escape(prefix) + r'[^：:]*[：:]\*\*\s*(.*)')
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if match:
            return match.group(1).strip()
    return ''


def _split_phrases(text):
    parts = re.split(r'[、，,；;／/\\|\n]+', text or '')
    seen, out = set(), []
    for part in parts:
        part = part.strip()
        if len(part) >= 2 and part not in seen:
            seen.add(part)
            out.append(part)
    return out


def _excluded_capabilities(body):
    """Capability phrases the contract explicitly excluded.

    Drawn from the 明确不做 / 明确排除项 bullets and any ``IC-*`` row whose
    grade is ``excluded``. The template leaves these fields blank, so an empty
    value simply means the project declared no exclusions.
    """
    caps = []
    for label in ('明确不做', '明确排除项'):
        value = _bullet_value(body, label)
        if value:
            caps.extend(_split_phrases(value))
    header, rows = _table(body, '约束', '对结构')
    grade_col = _column(header, '等级')
    cons_col = _column(header, '约束')
    if grade_col is not None and cons_col is not None:
        for row in rows:
            grade = row[grade_col].strip().strip('`').lower() \
                if grade_col < len(row) else ''
            if grade == 'excluded' and cons_col < len(row):
                caps.extend(_split_phrases(row[cons_col]))
    seen, out = set(), []
    for cap in caps:
        if cap not in seen:
            seen.add(cap)
            out.append(cap)
    return out


def _candidate_skin_blockers(body):
    """Block when declared visual candidates are skin-only or unevidenced.

    Mirrors the 换肤反模式 in visual-direction.md: two or more declared
    candidates must each carry structural-difference evidence (主布局容器 /
    核心组件形态 / 信息密度 / 首屏重心) and must not share one motif+composition
    pair. The swap-check conclusion stays prose: deciding it means reading
    negation in natural language, and "不是换肤" matched a bare 换肤 pattern,
    which blocked a correct contract. These two structural checks decide what
    a machine can decide; the prose is for the next reader.
    """
    blockers = []
    header, rows = _table(body, '候选', '设计主线')
    if not header:
        header, rows = _table(body, '候选', '母题')
    cand_col = _column(header, '候选')
    motif_col = _column(header, '设计主线', '母题')
    comp_col = _column(header, '构图命题')
    if cand_col is None or motif_col is None or comp_col is None:
        return blockers
    declared = []
    for row in rows:
        motif = row[motif_col].strip() if motif_col < len(row) else ''
        comp = row[comp_col].strip() if comp_col < len(row) else ''
        if motif or comp:
            declared.append((motif, comp))
    if len(declared) < 2:
        return blockers
    evidence = _bullet_after(body, '结构差异证据')
    if not evidence:
        blockers.append({
            'code': 'skin_only_candidates',
            'detail': '对照方向有≥2候选但缺少结构差异证据'
            '（主布局容器/核心组件形态/信息密度/首屏重心）'})
        return blockers
    pairs = {(motif, comp) for motif, comp in declared}
    if len(pairs) == 1:
        blockers.append({
            'code': 'skin_only_candidates',
            'detail': '候选设计主线与构图命题相同，仅可能换色/字体'})
    return blockers


def _extract_labels(text):
    """Label-ish strings: attribute values and element text of headings,
    buttons, links, list items, options, summaries and labels. Used to scope
    capability/logo matching away from prose and code."""
    labels = [m.group(1) for m in _ATTR_VAL_RE.finditer(text)]
    for match in _LABEL_TAG_RE.finditer(text):
        labels.append(_strip_tags(match.group('txt')))
    return labels


def _strip_tags(text):
    return re.sub(r'<[^>]+>', '', text).strip()


def _link_references(text):
    """Hrefs of ``<link>`` tags that can reference a package or asset bundle.

    Only stylesheet/preload/modulepreload tags count; metadata links
    (canonical, icon, alternate, manifest) point at page addresses, not at
    package specifiers. Attribute order is not assumed.
    """
    refs = []
    for tag in _LINK_TAG_RE.finditer(text):
        tag_text = tag.group(0)
        rel = _LINK_REL_RE.search(tag_text)
        if rel is None:
            continue
        roles = {token.lower() for token in rel.group(1).split()}
        if not roles & _ICON_LINK_RELS:
            continue
        href = _LINK_HREF_RE.search(tag_text)
        if href is not None:
            refs.append(href.group(1))
    return refs


def _detect_icon_systems(text):
    systems = set()
    refs = [m.group(1) for m in _IMPORT_RE.finditer(text)]
    refs += [m.group(1) for m in _LINK_SRC_RE.finditer(text)]
    refs += _link_references(text)
    for ref in refs:
        for sid, pattern in _ICON_SYSTEM_PACKAGES:
            if pattern.search(ref):
                systems.add(sid)
    for match in _CLASS_VAL_RE.finditer(text):
        for token in match.group(1).split():
            for sid, pattern in _ICON_CLASS_PREFIXES.items():
                if pattern.match(token):
                    systems.add(sid)
    for sid, pattern in _ICON_MARKUP_PATTERNS.items():
        if pattern.search(text):
            systems.add(sid)
    return systems


def _line_of(text, offset):
    return text.count('\n', 0, offset) + 1


def _length_preserving_blank(match):
    """Blank a comment without moving any reported line number."""
    return ''.join('\n' if char == '\n' else ' ' for char in match.group(0))


def _css_rule_blocks(text):
    """``(selector, body, offset)`` for each innermost declaration block.

    The selector is the text between the previous block, statement or tag and
    ``{`` -- enough to tell ``html`` / ``body`` from a component class. This is
    a scanner, not a CSS parser, and is only asked questions it can answer.
    """
    blocks = []
    for match in _CSS_BLOCK_RE.finditer(text):
        head = text[:match.end(1)]
        cut = max(head.rfind('}'), head.rfind('{'), head.rfind(';'),
                  head.rfind('>'))
        selector = re.sub(r'<[^>]*>', '', head[cut + 1:]).strip()
        blocks.append((selector, match.group(2), match.start(1)))
    return blocks


def _dead_ref_findings(root, rel, text):
    """Local references that point at nothing on disk.

    Returns ``(blocks_delivery, finding)`` pairs. A missing reference under a
    build-output directory is reported but not blocking: the file may be
    produced by a build step that has not run. Everywhere else it is the
    truncated-build tell -- the HTML exists, the stylesheet never got written,
    and the page renders as unstyled Times New Roman while every other check
    in this scan passes vacuously.
    """
    findings = []
    base = (root / rel).parent
    seen = set()
    scan = _COMMENT_RE.sub(_length_preserving_blank, text)
    refs = []
    for tag in _TAG_RE.finditer(scan):
        for attr in _ATTR_REF_RE.finditer(tag.group(0)):
            if not _BOUND_ATTR_RE.match(tag.group(0), attr.start()):
                continue
            refs.append((tag.start() + attr.start(),
                         attr.group(1) or attr.group(2) or ''))
    for css in _CSS_URL_RE.finditer(scan):
        refs.append((css.start(), css.group(1)))
    for css in _CSS_IMPORT_RE.finditer(scan):
        refs.append((css.start(), css.group(1)))
    for offset, raw in refs:
        raw = raw.strip()
        if not raw:
            continue
        ref = unquote(raw)
        if _SKIP_REF_RE.match(ref) or ref.startswith('/'):
            continue
        if _DYNAMIC_REF_RE.search(ref):
            continue
        path = ref.split('#')[0].split('?')[0]
        if not path or path in seen:
            continue
        seen.add(path)
        if (base / path).exists():
            continue
        parts = PurePath(path).parts
        build_output = bool(parts) and parts[0] in LINT_BUILD_OUTPUT_DIRS
        findings.append((not build_output, {
            'code': 'build_output_missing' if build_output else 'dead_local_ref',
            'file': rel, 'line': _line_of(scan, offset), 'ref': path,
            'detail': ('引用指向构建产物且当前不存在；确认是否还没构建，'
                       '或改掉这个引用' if build_output else
                       '引用的本地文件不存在；样式表缺失时整页会退化成无样式渲染'),
        }))
    return findings


def _static_rule_findings(root, rel, text):
    """``(blockers, warnings)`` from the contract-independent page rules."""
    blockers, warnings = [], []
    for blocks_delivery, finding in _dead_ref_findings(root, rel, text):
        (blockers if blocks_delivery else warnings).append(finding)

    suffix = PurePath(rel).suffix.lower()
    scan = _COMMENT_RE.sub(_length_preserving_blank, text)

    # A frame loop that reads geometry forces a synchronous layout on every
    # frame. The scan cannot prove the read sits inside the callback, so it
    # reports a question -- and a warning that is often wrong trains agents to
    # ignore warnings.
    if suffix in LINT_SCRIPT_SUFFIXES and _FRAME_LOOP_RE.search(scan):
        read = _LAYOUT_READ_RE.search(scan)
        if read:
            warnings.append({
                'code': 'layout_read_in_frame_loop', 'file': rel,
                'line': _line_of(scan, read.start()),
                'detail': '同一文件里既有 requestAnimationFrame 又有读取几何的调用'
                          '（getBoundingClientRect / offset* / client* / getComputedStyle）；'
                          '在逐帧循环里读这些值会强制同步重排。确认它们不在同一个'
                          '循环里，在的话把值缓到循环外读一次'})

    if suffix not in LINT_CSS_SUFFIXES:
        return blockers, warnings

    blocks = _css_rule_blocks(scan)

    # Animating a layout property invalidates style and layout every frame;
    # the compositor never sees it. ``transition: all`` is caught above.
    for declaration in _TRANSITION_DECL_RE.finditer(scan):
        prop = _LAYOUT_PROP_RE.search(declaration.group(1))
        if prop:
            warnings.append({
                'code': 'layout_property_transition', 'file': rel,
                'line': _line_of(scan, declaration.start()),
                'property': prop.group(0).lower(),
                'detail': f'过渡 {prop.group(0)} 每帧都会触发样式重算与布局；'
                          '改用 transform / opacity（宽度变化用 scaleX）'})
            break

    for selector, body, offset in blocks:
        if not _KEYFRAME_STEP_RE.match(selector):
            continue
        prop = None
        for declaration in _DECL_START_RE.finditer(body):
            if _LAYOUT_PROP_RE.fullmatch(declaration.group(1)):
                prop = declaration.group(1).lower()
                break
        if prop:
            warnings.append({
                'code': 'layout_property_animation', 'file': rel,
                'line': _line_of(scan, offset),
                'property': prop,
                'detail': f'动画里改了 {prop}，每帧触发样式重算与布局；'
                          '改用 transform / opacity'})
            break

    if _CONTINUOUS_MOTION_RE.search(scan) and not _REDUCED_MOTION_RE.search(scan):
        warnings.append({
            'code': 'motion_without_reduced_motion', 'file': rel,
            'detail': '页面有连续动效（rAF/gsap/@keyframes 等）但没有 '
                      'prefers-reduced-motion 降级；补一个定格状态'})

    if _TRANSITION_ALL_RE.search(scan):
        warnings.append({
            'code': 'transition_all', 'file': rel,
            'detail': 'transition: all 会连布局属性一起动画；改成要过渡的属性名'})

    for match in _GRADIENT_TEXT_RE.finditer(scan):
        window = scan[max(0, match.start() - 240):match.start() + 240]
        if _GRADIENT_RE.search(window):
            warnings.append({
                'code': 'gradient_text', 'file': rel,
                'line': _line_of(scan, match.start()),
                'detail': '标题字填充渐变是最容易识破的模板特征；改回单色'})
            break

    if re.search(r'position\s*:\s*sticky', scan, re.IGNORECASE):
        # overflow-x:hidden on html/body makes the element a scroll container,
        # which severs position:sticky for every descendant: the sideways
        # scroll stops and the nav stops sticking with it. Root selectors
        # only -- a card with hidden overflow is legitimate -- and gated on
        # the page using sticky at all, because without one nothing breaks.
        for selector, body, _offset in blocks:
            if _ROOT_SELECTOR_RE.match(selector) and re.search(
                    r'overflow(?:-x)?\s*:\s*hidden', body, re.IGNORECASE):
                warnings.append({
                    'code': 'overflow_hidden_with_sticky', 'file': rel,
                    'detail': 'html/body 上的 overflow-x:hidden 会切断 sticky；'
                              '改用 overflow-x: clip'})
                break

        sticky_at_zero = [
            offset for _selector, body, offset in blocks
            if re.search(r'position\s*:\s*sticky', body, re.IGNORECASE)
            and re.search(r'(?:^|[;\s])top\s*:\s*0(?:px|rem|em|%)?\s*(?:;|$)',
                          body, re.IGNORECASE)]
        if len(sticky_at_zero) >= 2:
            warnings.append({
                'code': 'dual_sticky_top0', 'file': rel,
                'line': _line_of(scan, sticky_at_zero[1]),
                'count': len(sticky_at_zero),
                'detail': '多个元素同时 sticky 在 top:0，滚动时会互相遮挡；'
                          '除导航外按 --nav-h 之类的偏移量错开'})

    for _selector, body, offset in blocks:
        if not re.search(r'text-transform\s*:\s*uppercase', body, re.IGNORECASE):
            continue
        leading = re.search(r'line-height\s*:\s*(0?\.\d+|\d(?:\.\d+)?)\s*(?:;|$)',
                            body, re.IGNORECASE)
        if leading and float(leading.group(1)) < 1:
            warnings.append({
                'code': 'uppercase_tight_leading', 'file': rel,
                'line': _line_of(scan, offset),
                'detail': '全大写没有下伸部，行高小于 1 时换行会让上排字母顶到上一行；'
                          '这类标题行高不低于 1.0'})

    # A bare ``1fr`` is ``minmax(auto, 1fr)``; a track holding an image floors
    # at the image's intrinsic width and the page scrolls sideways. Fires only
    # when the file really carries replaced content, and reports a question --
    # the scan cannot know the image sits in that track.
    has_image = re.search(r'<img\b|<picture\b|<video\b', scan, re.IGNORECASE)
    has_image_floor = re.search(
        r'(?:^|[\s,}>])(?:img|picture|video)[^{]*\{[^}]*max-width\s*:\s*100%',
        scan, re.IGNORECASE)
    if has_image and not has_image_floor:
        hits = []
        for _selector, body, offset in blocks:
            for decl in re.finditer(
                    r'grid-template-(?:columns|rows)\s*:\s*([^;}]+)', body,
                    re.IGNORECASE):
                stripped = re.sub(r'minmax\s*\([^)]*\)', 'MM', decl.group(1))
                if re.search(r'(?:^|[\s(,:])1fr\b', stripped):
                    hits.append(offset)
        if hits:
            warnings.append({
                'code': 'bare_fr_track', 'file': rel,
                'line': _line_of(scan, hits[0]), 'count': len(hits),
                'detail': '带图内容用了裸 1fr 的网格轨道；确认图片是否在这条轨道里，'
                          '是就改成 minmax(0, 1fr)'})

    # Token discipline: a scatter of opaque literals outside the token block
    # means the palette stopped being a system somewhere in the middle.
    without_tokens = _TOKEN_BLOCK_RE.sub(_length_preserving_blank, scan)
    literals = _OPAQUE_COLOR_RE.findall(without_tokens)
    if len(literals) > COLOR_LITERAL_LIMIT:
        warnings.append({
            'code': 'inline_color_literal', 'file': rel, 'count': len(literals),
            'detail': f'token 外有 {len(literals)} 个不透明颜色字面量；'
                      '提成语义 token 再引用'})

    return blockers, warnings


def _scan_file(rel, text, excepted_chars, icon_system, caps):
    """Return (blockers, warnings, had_icons) for one UI source file."""
    blockers, warnings = [], []
    had_icons = False
    stripped = _SCRIPT_STYLE_RE.sub('', text)

    # Rating clusters (≥3 stars) are fabricated social proof, not icons.
    seen_rating = set()
    for match in _STAR_RUN_RE.finditer(stripped):
        char = match.group(0)[0]
        if char in excepted_chars:
            continue
        line = _line_of(stripped, match.start())
        if line in seen_rating:
            continue
        seen_rating.add(line)
        had_icons = True
        blockers.append({'code': 'fabricated_proof', 'kind': 'fabricated_rating',
                         'file': rel, 'line': line, 'char': char,
                         'detail': '星级评定无来源'})

    # Emoji/Unicode used as a sole-content icon without a contract exception.
    seen = set()
    for match in _ICON_SOLO_RE.finditer(stripped):
        char = match.group(1)
        line = _line_of(stripped, match.start())
        if (line, char) in seen:
            continue
        seen.add((line, char))
        had_icons = True
        if char in excepted_chars:
            continue
        blockers.append({'code': 'emoji_icon_without_exception',
                         'file': rel, 'line': line, 'char': char,
                         'detail': 'Emoji/Unicode 充当按钮/导航/状态图标且无合同例外'})

    # Icon systems: two or more in one interface is a hard failure.
    systems = _detect_icon_systems(text)
    if systems:
        had_icons = True
    if len(systems) >= 2:
        blockers.append({'code': 'mixed_icon_systems', 'file': rel,
                         'systems': sorted(systems),
                         'detail': '同界面混用多套图标体系'})
    # A declared system (the user's or the project's own choice) wins; only an
    # undeclared contract falls back to the pack default. A file that does not
    # use the expected system is drift, not automatically a defect: the fix may
    # be either to align the code or to declare the choice in the contract.
    expected = icon_system or LUCIDE_ICON_SYSTEM
    if systems and expected not in systems:
        warnings.append({'code': 'icon_system_mismatch', 'file': rel,
                         'declared': icon_system or f'{LUCIDE_ICON_SYSTEM}（默认）',
                         'found': sorted(systems),
                         'detail': '实际图标体系与合同声明（或默认 Lucide）不一致；'
                                   '按用户指定改用声明体系，或把该选择写入合同'})

    # Fabricated proof: lorem-ipsum copy and placeholder logos.
    if _LOREM_RE.search(text):
        blockers.append({'code': 'fabricated_proof', 'kind': 'lorem_ipsum',
                         'file': rel, 'detail': 'Lorem ipsum 占位文案'})
    for match in _PLACEHOLDER_IMG_RE.finditer(text):
        line = _line_of(text, match.start())
        labels = _extract_labels(text)
        if any(_LOGO_CTX_RE.search(label) for label in labels):
            blockers.append({'code': 'fabricated_proof', 'kind': 'placeholder_logo',
                             'file': rel, 'line': line,
                             'detail': '占位图服务冒充客户 Logo / 品牌素材'})
        else:
            warnings.append({'code': 'placeholder_image', 'file': rel,
                             'line': line, 'detail': '占位图服务，核对是否为诚实缺图'})
        break

    # Explicitly excluded capabilities surfacing as UI affordances.
    if caps:
        labels = _extract_labels(text)
        matched = set()
        for cap in caps:
            if cap in matched:
                continue
            for label in labels:
                if cap in label:
                    matched.add(cap)
                    blockers.append({'code': 'excluded_capability_in_ui',
                                     'file': rel, 'capability': cap,
                                     'detail': '明确排除能力仍出现在界面'})
                    break

    return blockers, warnings, had_icons


# Template-tendency heuristics were removed here: hero+3-cards+CTA, card /
# pill / surface counts, and "any gradient or @keyframes". They were aesthetic
# judgments expressed as token counts, so they fired on layouts this package's
# own landing-page and dashboard guidance recommends, and a warning that is
# both non-blocking and frequently wrong trains agents to ignore warnings.
#
# Generated sameness is still caught where it can actually be judged:
# ``_candidate_skin_blockers`` hard-fails two declared directions that differ
# only by color and font, and ``check_contract`` requires each derived design
# judgment to cite a project fact. Aesthetic review stays in craft-review.md,
# where a reader can weigh context instead of a threshold.


def _is_exempt(rel_posix, exemptions):
    rel = PurePath(rel_posix)
    for pat in exemptions:
        if not pat:
            continue
        try:
            if rel.match(pat):
                return True
        except ValueError:
            pass
        if fnmatch.fnmatch(rel_posix, pat):
            return True
    return False


def _iter_ui_files(root):
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in LINT_IGNORE_DIRS for part in rel.parts):
            continue
        if any(part in LINT_FIXTURE_DIR_PARTS for part in rel.parts):
            continue
        if LINT_FIXTURE_NAME_RE.search(path.name):
            continue
        if path.suffix.lower() not in LINT_UI_EXTENSIONS:
            continue
        yield path


def _ui_manifest_sha256(entries):
    hasher = hashlib.sha256()
    found = False
    for rel, content in sorted(entries, key=lambda e: e[0]):
        found = True
        hasher.update(rel.encode('utf-8'))
        hasher.update(b'\0')
        hasher.update(hashlib.sha256(content).digest())
        hasher.update(b'\n')
    return hasher.hexdigest() if found else _sha256_bytes(b'')


# --- --changed-from: mirror stage 5's dual semantics (JSON report or git ref)

def _lint_git(root, *args):
    env = {'GIT_TERMINAL_PROMPT': '0'}
    try:
        proc = subprocess.run(['git', '-C', str(root), *args],
                              capture_output=True, env=env, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 128, b'', b''
    return proc.returncode, proc.stdout, proc.stderr


def _lint_git_repo(root):
    rc, out, _ = _lint_git(root, 'rev-parse', '--show-toplevel', '--show-prefix')
    if rc != 0:
        return None
    lines = out.decode('utf-8', 'replace').splitlines()
    if len(lines) < 2:
        return None
    return lines[0], lines[1]


def _lint_git_ui_hashes(root, ref, prefix):
    """UI source file hashes at ``ref`` via a single in-memory git archive.

    Mirrors stage 5's _git_source_sha256 but returns per-file hashes so the
    caller can scope to changed files. Returns None when the tree at ref is
    unreadable (caller treats ref as unresolvable).
    """
    pathspec = ['--', prefix] if prefix else []
    rc, out, _ = _lint_git(root, 'archive', '--format=tar', ref, *pathspec)
    if rc != 0 or not out:
        return None
    entries = {}
    try:
        tar = tarfile.open(fileobj=io.BytesIO(out), mode='r:')
    except tarfile.TarError:
        return None
    with tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name
            if prefix and name.startswith(prefix):
                name = name[len(prefix):]
            name = name.lstrip('/')
            if not name or Path(name).suffix.lower() not in LINT_UI_EXTENSIONS:
                continue
            parts = Path(name).parts
            if any(part in LINT_IGNORE_DIRS or part in LINT_FIXTURE_DIR_PARTS
                   for part in parts):
                continue
            if LINT_FIXTURE_NAME_RE.search(Path(name).name):
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            entries[name] = _sha256_bytes(extracted.read())
    return entries


def _resolve_lint_changed_from(root, ref, contract_file, current_contract_sha):
    """Resolve --changed-from into prior contract hash + per-file UI hashes.

    Dual semantics, like stage 5: a readable JSON lint-ui report (its
    ``contract_sha256`` and ``files`` are reused) or a git revision (the
    contract is read via ``git show`` and the UI tree re-fingerprinted via
    ``git archive``). Neither → machine-readable error and conservative full
    scan. A contract change since ref forces a full scan (the rules moved);
    otherwise the scan scopes to changed UI files. Stdlib only, no browser.
    """
    path = Path(ref)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict) and (
                'contract_sha256' in data or 'files' in data):
            prior_contract = data.get('contract_sha256')
            prior_files = {}
            for entry in data.get('files', []) or []:
                if isinstance(entry, dict) and entry.get('path') \
                        and entry.get('sha256'):
                    prior_files[str(entry['path'])] = str(entry['sha256'])
            contract_changed = (prior_contract is None
                                 or prior_contract != current_contract_sha)
            return {'available': True, 'source': 'json', 'commit': None,
                    'contract_changed': contract_changed,
                    'prior_files': prior_files, 'error': None}
        # A readable file that is not a usable report falls through to git.
    repo = _lint_git_repo(root)
    if repo is None:
        return {'available': False, 'source': None, 'commit': None,
                'contract_changed': True, 'prior_files': {},
                'error': f'ref is neither a readable JSON lint-ui report nor a '
                         f'resolvable git revision: {ref}'}
    _toplevel, prefix = repo
    rc, out, _ = _lint_git(root, 'rev-parse', '--verify', f'{ref}^{{commit}}')
    if rc != 0 or not out.strip():
        return {'available': False, 'source': 'git', 'commit': None,
                'contract_changed': True, 'prior_files': {},
                'error': f'git revision does not resolve to a commit: {ref}'}
    commit = out.decode('utf-8', 'replace').strip()
    try:
        contract_rel_to_root = contract_file.relative_to(root).as_posix()
    except ValueError:
        contract_rel_to_root = None
    prior_contract = None
    if contract_rel_to_root is not None:
        rc, out, _ = _lint_git(root, 'show',
                               f'{ref}:{prefix + contract_rel_to_root}')
        if rc == 0:
            prior_contract = _sha256_bytes(out)
        # rc != 0: contract absent at ref → conservatively changed
    prior_files = _lint_git_ui_hashes(root, ref, prefix)
    if prior_files is None:
        return {'available': False, 'source': 'git', 'commit': commit,
                'contract_changed': True, 'prior_files': {},
                'error': f'source tree at ref is unreadable: {ref}'}
    contract_changed = prior_contract is None or prior_contract != current_contract_sha
    return {'available': True, 'source': 'git', 'commit': commit,
            'contract_changed': contract_changed, 'prior_files': prior_files,
            'error': None}


def lint_ui(root, contract_rel, changed_from=None):
    """Statically lint the project UI against the design contract.

    Reads the contract for the declared icon system, emoji/unicode exceptions,
    excluded capabilities and visual-candidate evidence, then scans UI source
    files under ``root`` for the deterministic anti-patterns defined in
    craft-review.md §6. Determined problems are blockers; templating
    tendencies are warnings. ``--changed-from`` scopes the scan to UI files
    that changed since a prior report or git revision.
    """
    root = Path(root).resolve()
    contract_file = Path(contract_rel)
    if not contract_file.is_absolute():
        contract_file = root / contract_rel
    blockers, warnings = [], []

    try:
        contract_text = contract_file.read_text(encoding='utf-8')
    except (OSError, ValueError) as error:
        return _lint_report(root, contract_rel, '', False,
                            [{'code': 'missing_contract', 'detail': str(error)}],
                            warnings, None, [], None, [])

    sha = _sha256_bytes(contract_text.encode('utf-8'))
    body = _strip_contract_block(contract_text)
    try:
        data = _parse_contract_block(contract_text)
        lists = _contract_lists(data)
    except ValueError as error:
        return _lint_report(root, contract_rel, sha, False,
                            [{'code': 'invalid_contract', 'detail': str(error)}],
                            warnings, None, [], None, [])

    icon_system = str(data.get('icon_system') or '').strip().lower()
    exceptions_raw = data.get('icon_exceptions', [])
    excepted_chars, icon_exceptions = set(), []
    if isinstance(exceptions_raw, list):
        for item in exceptions_raw:
            if isinstance(item, dict) and item.get('char'):
                excepted_chars.add(str(item['char']))
                icon_exceptions.append({'char': str(item['char']),
                                        'basis': str(item.get('basis') or '')})
            elif isinstance(item, str) and item:
                excepted_chars.add(item)
                icon_exceptions.append({'char': item, 'basis': ''})
    exemptions = list(lists.get('intentional_exceptions', []))

    caps = _excluded_capabilities(body)
    blockers.extend(_candidate_skin_blockers(body))

    cf = None
    if changed_from:
        cf = _resolve_lint_changed_from(root, changed_from, contract_file, sha)

    # First pass: enumerate UI files (honoring exemptions) and hash them.
    current_files = {}
    for path in _iter_ui_files(root):
        rel = path.relative_to(root).as_posix()
        if _is_exempt(rel, exemptions):
            continue
        current_files[rel] = path.read_bytes()
    current_hashes = {rel: _sha256_bytes(content)
                      for rel, content in current_files.items()}
    file_hashes = [{'path': rel, 'sha256': digest}
                   for rel, digest in current_hashes.items()]
    ui_sha = _ui_manifest_sha256(list(current_files.items()))

    # Decide the file scan scope. A contract change since ref forces a full
    # scan (the rules moved); an unavailable ref also scans everything. Only a
    # resolved, contract-stable ref scopes to the UI files that changed.
    changed_summary = None
    scan_set = None
    if cf is not None:
        prior = cf['prior_files']
        changed_count = sum(1 for rel, digest in current_hashes.items()
                            if rel not in prior or prior.get(rel) != digest)
        scoped = cf['available'] and not cf['contract_changed']
        if scoped:
            scan_set = {rel for rel, digest in current_hashes.items()
                        if rel not in prior or prior.get(rel) != digest}
        changed_summary = {
            'ref': changed_from, 'available': cf['available'],
            'source': cf['source'], 'commit': cf.get('commit'),
            'contract_changed': cf['contract_changed'],
            'changed_files': changed_count, 'scoped': scoped,
            'error': cf.get('error'),
        }

    iterable = scan_set if scan_set is not None else current_hashes.keys()
    scanned = []
    had_icons = False
    for rel in sorted(iterable):
        text = current_files[rel].decode('utf-8', errors='replace')
        scanned.append(rel)
        file_blockers, file_warnings, icons = _scan_file(
            rel, text, excepted_chars, icon_system, caps)
        blockers.extend(file_blockers)
        warnings.extend(file_warnings)
        static_blockers, static_warnings = _static_rule_findings(root, rel, text)
        blockers.extend(static_blockers)
        warnings.extend(static_warnings)
        if icons:
            had_icons = True

    if had_icons and not icon_system:
        warnings.append({'code': 'undeclared_icon_system',
                         'detail': '界面使用图标但合同未声明 icon_system（默认 Lucide）；'
                                   '采用其他体系时显式声明即可'})

    return _lint_report(root, contract_rel, sha, not blockers, blockers,
                        warnings, changed_summary, scanned, ui_sha,
                        file_hashes)


def _lint_report(root, contract_rel, sha, passed, blockers, warnings,
                 changed_from, scanned, ui_sha, files):
    return {
        'project_root': str(root),
        'contract_path': contract_rel,
        'contract_sha256': sha,
        'ui_source_sha256': ui_sha if ui_sha is not None else '',
        'scanned_files': scanned if scanned is not None else [],
        'files': files if files is not None else [],
        'changed_from': changed_from,
        'blockers': blockers,
        'warnings': warnings,
        'not_covered': list(LINT_NOT_COVERED),
        'passed': passed,
        'checked_at': _now(),
    }


# --- bounded stdout (--summary) -------------------------------------------
# The full report is the artifact that belongs on disk. Printed verbatim it
# also scales with the project: lint-ui emits one manifest entry per scanned
# UI file, so a few hundred components push tens of kilobytes of hashes into a
# caller that only reads the verdict. --summary keeps stdout bounded to counts
# plus the first findings; --out still receives the complete report.

SUMMARY_FINDING_LIMIT = 5
SUMMARY_PASSTHROUGH_KEYS = ('phase', 'ui_source_sha256', 'changed_from')
SUMMARY_COUNT_KEYS = (('scanned_files', 'scanned_file_count'),
                      ('files', 'tracked_file_count'))


def _report_summary(report, report_path=None, max_findings=SUMMARY_FINDING_LIMIT):
    """Bounded stdout view of a full report: counts plus a capped sample."""
    blockers = list(report.get('blockers') or [])
    warnings = list(report.get('warnings') or [])
    omitted = {'blockers': max(0, len(blockers) - max_findings),
               'warnings': max(0, len(warnings) - max_findings)}
    summary = {
        'mode': 'summary',
        'passed': report.get('passed'),
        'project_root': report.get('project_root'),
        'contract_path': report.get('contract_path'),
        'contract_sha256': report.get('contract_sha256'),
        'blocker_count': len(blockers),
        'warning_count': len(warnings),
        'blockers': blockers[:max_findings],
        'warnings': warnings[:max_findings],
        'omitted': omitted,
    }
    for key in SUMMARY_PASSTHROUGH_KEYS:
        if key in report:
            summary[key] = report[key]
    if report.get('not_covered'):
        summary['not_covered'] = report['not_covered']
    for key, target in SUMMARY_COUNT_KEYS:
        if key in report:
            summary[target] = len(report.get(key) or [])
    if omitted['blockers'] or omitted['warnings']:
        summary['note'] = (
            'findings truncated; the complete list is in the report file'
            if report_path else
            'findings truncated; rerun with --out <path> for the complete list '
            'or --max-findings N to widen stdout')
    summary['report'] = str(report_path) if report_path else None
    summary['checked_at'] = report.get('checked_at')
    return summary


def _emit_report(args, report):
    """Write the full report when --out is given, then print it or its summary."""
    text = json.dumps(report, ensure_ascii=False, indent=2)
    report_path = None
    if args.out:
        report_path = args.out.expanduser()
        report_path.write_text(text + '\n', encoding='utf-8')
        report_path = report_path.resolve()
    if args.summary:
        limit = SUMMARY_FINDING_LIMIT if args.max_findings is None else args.max_findings
        print(json.dumps(_report_summary(report, report_path, limit),
                         ensure_ascii=False, indent=2))
    else:
        print(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    validate_cmd = commands.add_parser('validate')
    validate_cmd.add_argument('--auto-sync', action='store_true', help='automatically synchronize gallery catalog payload if stale')
    commands.add_parser('catalog', help='list bundled design domains, stacks, and query contract')
    lookup = commands.add_parser('research', help='query the bundled UI/UX design intelligence')
    lookup.add_argument('query', help='2-5 terms describing one design intent')
    lookup_mode = lookup.add_mutually_exclusive_group(required=True)
    lookup_mode.add_argument('--design-system', action='store_true', help='generate a direction candidate set')
    lookup_mode.add_argument('--domain', choices=INTELLIGENCE_DOMAINS, help='search one design domain')
    lookup_mode.add_argument('--stack', choices=INTELLIGENCE_STACKS, help='search guidance for a detected implementation stack')
    lookup.add_argument('--project-name')
    lookup.add_argument('--max-results', type=int, choices=range(1, 21), default=3)
    lookup.add_argument('--variance', type=int, choices=range(1, 11))
    lookup.add_argument('--motion', type=int, choices=range(1, 11))
    lookup.add_argument('--density', type=int, choices=range(1, 11))
    sync = commands.add_parser('sync-gallery', help='refresh the gallery catalog payload from tokens.json')
    sync.add_argument('--gallery', type=Path, default=resources() / 'gallery.html')
    check = commands.add_parser(
        'check-contract',
        help='check the project design contract and emit a machine-readable report')
    check.add_argument('--root', type=Path, required=True, help='project root containing .site/design/surface-brief.md')
    check.add_argument('--phase', required=True, choices=list(CONTRACT_PHASES))
    check.add_argument('--out', type=Path, help='write the report JSON to this path as well as stdout')
    lint = commands.add_parser(
        'lint-ui',
        help='statically lint the project UI against the design contract')
    lint.add_argument('--root', type=Path, required=True,
                       help='project root containing the UI source to scan')
    lint.add_argument('--contract', default=CONTRACT_REL_PATH,
                      help='contract path, relative to root or absolute')
    lint.add_argument('--changed-from', default=None,
                      help='a prior lint-ui report JSON path OR a git revision '
                           '(branch/tag/commit); scopes the scan to UI files '
                           'that changed since it. An REF that is neither is '
                           'reported and conservatively scans everything')
    lint.add_argument('--out', type=Path,
                       help='write the report JSON to this path as well as stdout')
    for command in (check, lint):
        command.add_argument('--summary', action='store_true',
                             help='print a bounded summary (counts and the first '
                                  'findings) instead of the full report; --out still '
                                  'writes the complete report')
        command.add_argument('--max-findings', type=int, default=None, metavar='N',
                             help='findings listed per severity with --summary '
                                  f'(default {SUMMARY_FINDING_LIMIT})')
    build = commands.add_parser('build')
    build.add_argument('--recipe', required=True,
                       help='recipe key; run `design.py list` for the catalog '
                            'and each recipe default combination')
    for key in GROUPS:
        build.add_argument('--' + key,
                           help=f'override the recipe default {key}; '
                                f'run `design.py list` for valid keys')
    build.add_argument('--out', type=Path, required=True, help='New or empty output directory')
    build.add_argument('--project-root', type=Path, default=Path.cwd(),
                       help='project root holding .site/design/surface-brief.md; '
                            'the direction gate reads the contract from here '
                            '(default: current directory)')
    build.add_argument('--standalone', action='store_true',
                       help='skip the direction gate when no project direction '
                            'exists yet; the selection is then marked as having '
                            'no direction evidence')
    args = parser.parse_args()
    try:
        if getattr(args, 'max_findings', None) is not None:
            if not args.summary:
                raise ValueError('--max-findings requires --summary')
            if args.max_findings < 0:
                raise ValueError('--max-findings must be zero or greater')

        if args.command == 'research':
            if not args.design_system and any(
                    getattr(args, name) is not None for name in ('project_name', 'variance', 'motion', 'density')):
                raise ValueError('--project-name/--variance/--motion/--density require --design-system')
            print(json.dumps(research(args), ensure_ascii=False, indent=2))
            return

        if args.command == 'catalog':
            print(json.dumps(intelligence_catalog(), ensure_ascii=False, indent=2))
            return

        if args.command == 'check-contract':
            _emit_report(args, check_contract(args.root, args.phase))
            return

        if args.command == 'lint-ui':
            _emit_report(args, lint_ui(args.root, args.contract, args.changed_from))
            return

        data = read_catalog()
        if args.command == 'list':
            print(json.dumps({'recipes': data['recipes'], 'profiles': {key: list(data[group]) for key, group in GROUPS.items()}}, ensure_ascii=False, indent=2))
        elif args.command == 'validate':
            for recipe in data['recipes']:
                compose(data, recipe)
            for palette in data['palettes']:
                compose(data, next(iter(data['recipes'])), palette=palette)
            gallery = resources() / 'gallery.html'
            drift = gallery_catalog_drift(data)
            if drift == STALE_CATALOG:
                if getattr(args, 'auto_sync', False):
                    sync_gallery(data, gallery)
                    print(f"[Auto-Sync] Gallery catalog payload was stale and has been updated in {gallery.resolve()}")
                    drift = None
                else:
                    script_name = Path(sys.argv[0]).name or 'design.py'
                    drift = (f'{drift}; run: python {script_name} sync-gallery '
                             f'--gallery "{gallery.resolve()}" (or run validate with --auto-sync)')
            if drift:
                raise ValueError(drift)
            intelligence = validate_intelligence()
            print(f"{len(data['recipes'])} recipes and {len(data['palettes'])} palettes passed listed color-pair and typography-floor checks; gallery catalog in sync. {intelligence}")
        elif args.command == 'sync-gallery':
            gallery = args.gallery.expanduser()
            changed = sync_gallery(data, gallery)
            print(json.dumps({'gallery': str(gallery.resolve()), 'catalog_version': data['version'],
                              'recipes': len(data['recipes']), 'changed': changed}, ensure_ascii=False))
        else:
            # The catalogue is the only artifact one command away. Refuse to
            # hand out ready-to-use tokens until the project's own direction
            # exists, and make the way around that gate explicit and recorded.
            evidence = {'mode': 'standalone', 'contract_sha256': None}
            if not args.standalone:
                gate = direction_gate(args.project_root)
                if not gate['passed']:
                    codes = ', '.join(sorted({entry['code'] for entry in gate['blockers']}))
                    raise ValueError(
                        '方向未确认，禁止选择配方（' + (codes or 'unknown') + '）。先补齐 '
                        'surface-brief.md 的设计主线、反默认原因、构图命题与细节签名，'
                        '每项引用一条合同已声明的项目事实，再重跑；'
                        '确认这只是一份无方向依据的草稿时才加 --standalone。')
                evidence = {'mode': 'direction-gate',
                            'contract_sha256': gate['contract_sha256']}
            result = compose(data, args.recipe, **{key: getattr(args, key) for key in GROUPS})
            result['direction_evidence'] = evidence
            dest = args.out.expanduser()
            if dest.is_symlink() or (dest.exists() and (not dest.is_dir() or any(dest.iterdir()))):
                raise ValueError('Output must be a new or empty directory; existing files preserved')
            dest.mkdir(parents=True, exist_ok=True)
            (dest / 'tokens.css').write_text(css_text(result), encoding='utf-8')
            (dest / 'selection.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            (dest / 'intent.md').write_text(intent_text(result), encoding='utf-8')
            print(json.dumps({'output': str(dest.resolve()), 'token_count': len(result['tokens']),
                              'recipe': result['recipe'], 'selection': result['selection'],
                              'direction_evidence': evidence,
                              'files': ['tokens.css', 'selection.json', 'intent.md']}, ensure_ascii=False))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
