"""Compose portable design tokens and a local gallery. Python 3.10+, no dependencies."""
import argparse
import json
from pathlib import Path
import re
import sys

GROUPS = {'palette': 'palettes', 'typography': 'typographies', 'density': 'densities',
          'shape': 'shapes', 'layout': 'layouts'}


def resources():
    here = Path(__file__).resolve().parent
    return here / 'design' if (here / 'design/tokens.json').exists() else here.parent / 'assets/design'


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


# Craft floors taken from references/typography.md.  They guard the catalog's own
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    commands.add_parser('validate')
    sync = commands.add_parser('sync-gallery', help='refresh the gallery catalog payload from tokens.json')
    sync.add_argument('--gallery', type=Path, default=resources() / 'gallery.html')
    build = commands.add_parser('build')
    build.add_argument('--recipe', required=True)
    for key in GROUPS:
        build.add_argument('--' + key)
    build.add_argument('--out', type=Path, required=True, help='New or empty output directory')
    args = parser.parse_args()
    try:
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
            print(f"{len(data['recipes'])} recipes and {len(data['palettes'])} palettes passed listed color-pair and typography-floor checks; gallery catalog in sync.")
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
