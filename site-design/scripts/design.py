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
    return {'catalog_version': data['version'], 'recipe': recipe, 'selection': selection,
            'tokens': tokens, 'color_checks': results,
            'layout_guidance': data['layouts'][selection['layout']]['guidance'],
            'limits': ['Opaque listed color pairs only; not full accessibility or visual acceptance.',
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    commands.add_parser('validate')
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
            print(f"{len(data['recipes'])} recipes and {len(data['palettes'])} palettes passed listed color-pair checks.")
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
