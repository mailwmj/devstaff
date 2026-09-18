"""Research directions and compose portable design tokens. Python 3.10+, stdlib only."""
import argparse
import fnmatch
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path, PurePath
import re
import subprocess
import sys
from datetime import datetime, timezone

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
        command, text=True, capture_output=True, env=intelligence_environment())
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or 'unknown error'
        raise ValueError('Bundled design intelligence failed: ' + detail)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError('Bundled design intelligence returned invalid JSON') from error

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
        env=intelligence_environment())
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
        return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
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


def compose(data, recipe, **overrides):
    if recipe not in data['recipes']:
        raise ValueError(f'Unknown recipe: {recipe}')
    chosen = data['recipes'][recipe]
    unknown = set(overrides) - set(GROUPS)
    if unknown:
        raise ValueError(f'Unknown override groups: {sorted(unknown)}')
    selection = {key: overrides.get(key) or chosen[key] for key in GROUPS}
    tokens = dict(data['base'])
    for key, group in GROUPS.items():
        if selection[key] not in data[group]:
            raise ValueError(f'Unknown {key}: {selection[key]}')
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
    return f'''# 项目设计意图

> 这是由 `{result['recipe']}` 生成的实现校准草稿。它需要结合项目方向合同填写，不代表用户已确认设计方向。

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
    'components', 'assets', 'acceptance', 'unresolved_confirm',
    'blocking_missing_assets', 'intentional_exceptions',
)
# Design-judgment aspects that must be formed from project facts, not copied
# from the template. Each names the bullet label(s) in surface-brief.md; a
# value that still equals the template default means the field was not filled.
PROJECT_FACT_LABELS = ('使用者', '主任务', '业务对象', '真实内容')
DESIGN_JUDGMENT_ASPECTS = (
    ('project_facts', PROJECT_FACT_LABELS),
    ('anti_default', ('反默认原因',)),
    ('visual_motif', ('母题',)),
    ('composition', ('构图命题',)),
    ('detail_signature', ('细节签名',)),
)
VAGUE_VA_TERMS = ('高级', '现代', '像参考', '时尚', '优雅', '大气', '精致')
CONTRACT_PHASES = ('direction', 'prebuild', 'precheck')


def template_path():
    return Path(__file__).resolve().parent.parent / 'references' / 'surface-brief.md'


def contract_path(root):
    for rel in (CONTRACT_REL_PATH, '.SITE/design/surface-brief.md', '.v3/design/surface-brief.md'):
        candidate = Path(root) / rel
        if candidate.is_file():
            return candidate
    return Path(root) / CONTRACT_REL_PATH


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


def _missing_design_judgment(body, template_body):
    """Aspects still equal to the template default (not filled from project facts)."""
    missing = []
    for aspect, labels in DESIGN_JUDGMENT_ASPECTS:
        present = False
        for label in labels:
            value = _bullet_value(body, label)
            default = _bullet_value(template_body, label)
            if value and value != default:
                present = True
                break
        if not present:
            missing.append(aspect)
    return missing


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
    are blockers; templating tendencies are warnings. The report's SHA-256 is
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
                      'responsive', 'components', 'assets', 'acceptance')
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
                    warnings.append({'code': 'vague_va_standard', 'ref': va,
                                     'terms': vague})

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
        try:
            template_body = _strip_contract_block(template_path().read_text(encoding='utf-8'))
        except OSError:
            template_body = ''
        for aspect in _missing_design_judgment(body, template_body):
            blockers.append({'code': 'missing_design_judgment', 'aspect': aspect})

    return _contract_report(root, phase, sha, not blockers, blockers, warnings)


# --- UI lint (stage 3) ------------------------------------------------------
# lint-ui reads the project contract (declared icon system, emoji/unicode
# exceptions, excluded capabilities, visual-candidate evidence) and statically
# scans the project's UI source for deterministic anti-patterns. It is a
# read-only, stdlib-only check: it never starts a browser. Determined problems
# are blockers; templating tendencies are warnings. Output is machine-readable
# JSON. Real user content, test fixtures, Markdown and data files are excluded
# from the scan; contract ``intentional_exceptions`` that look like paths or
# globs exempt matching files.

LINT_UI_EXTENSIONS = ('.html', '.htm', '.css', '.js', '.mjs', '.cjs',
                      '.jsx', '.ts', '.tsx', '.vue', '.svelte', '.astro')
LINT_IGNORE_DIRS = {'.site', '.SITE', '.v3', '.git', 'node_modules', '__pycache__', '.DS_Store',
                    'dist', 'build', '.next', '.nuxt', '.svelte-kit',
                    '.output', 'coverage', '.turbo', '.vercel', '.astro'}
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
_LINK_SRC_RE = re.compile(r'<(?:link|script)\b[^>]*\bsrc=["\']([^"\']+)["\']',
                          re.IGNORECASE)
_LINK_HREF_RE = re.compile(r'<link\b[^>]*\bhref=["\']([^"\']+)["\']',
                           re.IGNORECASE)
_CLASS_VAL_RE = re.compile(r'(?:class|className)=["\']([^"\']*)["\']',
                           re.IGNORECASE)
_LABEL_TAG_RE = re.compile(
    r'<(?P<tag>h[1-6]|button|a|li|option|summary|label)\b[^>]*>'
    r'(?P<txt>.*?)</(?P=tag)>', re.IGNORECASE | re.DOTALL)
_ATTR_VAL_RE = re.compile(
    r'(?:class|className|id|alt|aria-label|placeholder|title|role)=["\']'
    r'([^"\']*)["\']', re.IGNORECASE)

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


def _excluded_capabilities(body, template_body):
    """Capability phrases the contract explicitly excluded.

    Drawn from the 明确不做 / 明确排除项 bullets and any ``IC-*`` row whose
    grade is ``excluded``. Template-default values mean the project did not
    declare exclusions, so nothing is extracted.
    """
    caps = []
    for label in ('明确不做', '明确排除项'):
        value = _bullet_value(body, label)
        default = _bullet_value(template_body, label)
        if value and value != default:
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


def _candidate_skin_blockers(body, template_body):
    """Block when declared visual candidates are skin-only or unevidenced.

    Mirrors the 换肤反模式 in visual-direction.md: two or more declared
    candidates must each carry structural-difference evidence (主布局容器 /
    核心组件形态 / 信息密度 / 首屏重心). Missing evidence, identical
    motif+composition across candidates, or a swap-check that admits换肤 are
    all hard failures — color/font-only differences are not a second direction.
    """
    blockers = []
    header, rows = _table(body, '候选', '母题')
    cand_col = _column(header, '候选')
    motif_col = _column(header, '母题')
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
    default = _bullet_after(template_body, '结构差异证据')
    if not evidence or evidence == default:
        blockers.append({
            'code': 'skin_only_candidates',
            'detail': '对照方向有≥2候选但缺少结构差异证据'
            '（主布局容器/核心组件形态/信息密度/首屏重心）'})
        return blockers
    pairs = {(motif, comp) for motif, comp in declared}
    if len(pairs) == 1:
        blockers.append({
            'code': 'skin_only_candidates',
            'detail': '候选母题与构图命题相同，仅可能换色/字体'})
    swap = _bullet_after(body, '交换检查结论')
    if swap and re.search(r'换肤|差异(?:不|基本.*不)成立|基本消失|只(?:是|能算).*上色',
                          swap):
        blockers.append({
            'code': 'skin_only_candidates',
            'detail': '交换检查结论表明候选仅换肤：' + swap})
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


def _detect_icon_systems(text):
    systems = set()
    refs = [m.group(1) for m in _IMPORT_RE.finditer(text)]
    refs += [m.group(1) for m in _LINK_SRC_RE.finditer(text)]
    refs += [m.group(1) for m in _LINK_HREF_RE.finditer(text)]
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
    elif icon_system and systems and icon_system not in systems:
        warnings.append({'code': 'icon_system_mismatch', 'file': rel,
                         'declared': icon_system, 'found': sorted(systems)})

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

    warnings.extend(_template_warnings(rel, text))
    return blockers, warnings, had_icons


def _template_warnings(rel, text):
    warnings = []
    cards = len(re.findall(r'class=["\'][^"\']*\bcard\b|<article\b', text,
                           re.IGNORECASE))
    hero = bool(re.search(r'class=["\'][^"\']*\bhero\b|\bid=["\']\s*hero\b',
                          text, re.IGNORECASE))
    cta = bool(re.search(
        r'<(?:button|a)\b[^>]*>[^<]{0,30}'
        r'(?:开始|立即|免费|订阅|联系|注册|登录|加入|了解更多|Get started|Sign up|'
        r'Subscribe|Contact|Start now|Try|Buy|Join|Learn more)', text,
        re.IGNORECASE))
    if hero and cards >= 3 and cta:
        warnings.append({'code': 'template_hero_cards_cta', 'file': rel,
                         'detail': 'Hero+三卡+CTA 生成式骨架'})
    if cards >= 4:
        warnings.append({'code': 'template_card_soup', 'file': rel,
                         'detail': '满页同规格卡片'})
    pills = len(re.findall(r'class=["\'][^"\']*\b(?:pill|badge|chip|tag)\b',
                           text, re.IGNORECASE))
    if pills >= 4:
        warnings.append({'code': 'template_pill_badge_soup', 'file': rel,
                         'detail': '多处 pill/badge/chip/tag'})
    if re.search(r'backdrop-filter|filter:\s*[^;}]*blur'
                 r'|(?:linear|radial)-gradient', text, re.IGNORECASE):
        warnings.append({'code': 'template_unsourced_effects', 'file': rel,
                         'detail': '无来源渐变/玻璃/光晕'})
    surfaces = len(re.findall(r'class=["\'][^"\']*\bsurface\b', text,
                              re.IGNORECASE))
    if surfaces >= 3:
        warnings.append({'code': 'template_section_surfaces', 'file': rel,
                         'detail': '每区块独立 surface'})
    if re.search(r'@keyframes|\banimation\s*:', text, re.IGNORECASE):
        warnings.append({'code': 'template_decorative_animation', 'file': rel,
                         'detail': '装饰动画须有状态/因果依据'})
    return warnings


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

    try:
        template_body = _strip_contract_block(
            template_path().read_text(encoding='utf-8'))
    except OSError:
        template_body = ''
    caps = _excluded_capabilities(body, template_body)
    blockers.extend(_candidate_skin_blockers(body, template_body))

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
        if icons:
            had_icons = True

    if had_icons and not icon_system:
        warnings.append({'code': 'undeclared_icon_system',
                         'detail': '界面使用图标但合同未声明 icon_system'})

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
        'passed': passed,
        'checked_at': _now(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    commands.add_parser('validate')
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
    build = commands.add_parser('build')
    build.add_argument('--recipe', required=True)
    for key in GROUPS:
        build.add_argument('--' + key)
    build.add_argument('--out', type=Path, required=True, help='New or empty output directory')
    args = parser.parse_args()
    try:
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
            report = check_contract(args.root, args.phase)
            text = json.dumps(report, ensure_ascii=False, indent=2)
            if args.out:
                args.out.expanduser().write_text(text + '\n', encoding='utf-8')
            print(text)
            return

        if args.command == 'lint-ui':
            report = lint_ui(args.root, args.contract, args.changed_from)
            text = json.dumps(report, ensure_ascii=False, indent=2)
            if args.out:
                args.out.expanduser().write_text(text + '\n', encoding='utf-8')
            print(text)
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
            drift = ''
            if gallery.is_file():
                match = CATALOG_BLOCK.search(gallery.read_text(encoding='utf-8'))
                expected = json.dumps(
                    {key: {**value, **compose(data, key)} for key, value in data['recipes'].items()},
                    ensure_ascii=False).replace('<', '\\u003c')
                if not match:
                    drift = 'Gallery has no <script id="catalog"> block.'
                elif match.group(2) != expected:
                    drift = 'Gallery catalog payload is stale; run: design.py sync-gallery'
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
            result = compose(data, args.recipe, **{key: getattr(args, key) for key in GROUPS})
            dest = args.out.expanduser()
            if dest.is_symlink() or (dest.exists() and (not dest.is_dir() or any(dest.iterdir()))):
                raise ValueError('Output must be a new or empty directory; existing files preserved')
            dest.mkdir(parents=True, exist_ok=True)
            (dest / 'tokens.css').write_text(css_text(result), encoding='utf-8')
            (dest / 'selection.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            (dest / 'intent.md').write_text(intent_text(result), encoding='utf-8')
            print(json.dumps({'output': str(dest.resolve()), 'token_count': len(result['tokens']),
                              'recipe': result['recipe'], 'selection': result['selection'],
                              'files': ['tokens.css', 'selection.json', 'intent.md']}, ensure_ascii=False))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
