#!/usr/bin/env node
// 生成规范库的机器可读目录：assets/spec/catalog.json
//
// 规范正文不在此处改写。本工具只做语义索引与体检：
//   - 从 frontmatter 提取语义色、字体角色、圆角
//   - 用 profiles.json 补齐选择所需的任务、内容、受众、信任、素材与交互信息
//   - 用相对亮度自行判断明暗（上游 parser 的 detectDarkTheme 会误判，见 KNOWN-ISSUES）
//   - 报告重复 YAML 键、对比度风险、CJK 字体缺失
//
// 用法：
//   node tools/catalog.mjs            # 重新生成 catalog.json
//   node tools/catalog.mjs --check    # 只校验 catalog.json 是否与规范一致（CI 用）

import { readFileSync, writeFileSync, readdirSync, existsSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SPEC_ROOT = join(HERE, '..', 'assets', 'spec');
const OUT = join(SPEC_ROOT, 'catalog.json');
const PROFILES = join(SPEC_ROOT, 'profiles.json');
const CHECK = process.argv.includes('--check');

// ---------- 颜色数学（WCAG 2.1 相对亮度） ----------
export function relLuminance(hex) {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h;
  if (!/^[0-9A-Fa-f]{6}$/.test(full)) return null;
  const [r, g, b] = [0, 2, 4]
    .map(i => parseInt(full.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a, b) {
  const la = relLuminance(a), lb = relLuminance(b);
  if (la === null || lb === null) return null;
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

// ---------- frontmatter ----------
function splitFrontMatter(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  return m ? m[1] : '';
}

// 上游 frontmatter 是简化的 key: "value" 形式，不是完整 YAML。
//
// 重要：约 10 份规范把「亮色块 + 暗色块」叠在同一个 colors: 里，键会重复。
// 任何取后者的解析器（含上游自己的 parser.mjs）都会得到拼接错的混合主题——
// 例如 02-tech-minimal 会变成 surface=#111111 配 on-surface=#0A0A0A（对比度 1.05）。
// 这里按「出现次序」拆成第 1 块 / 第 2 块，第 1 块通常是自洽的亮色主题。
function parseColorBlock(fm) {
  const lines = fm.split(/\r?\n/);
  const start = lines.findIndex(l => /^colors:\s*$/.test(l));
  if (start === -1) return { colors: {}, colorsDark: {}, duplicates: [], blocks: 0 };

  const occurrences = new Map(); // key -> [hex, ...]
  const order = [];
  for (let i = start + 1; i < lines.length; i++) {
    const line = lines[i];
    if (/^\S/.test(line)) break; // 下一个顶层键
    const m = line.match(/^\s{2}([a-z0-9-]+):\s*"?(#[0-9A-Fa-f]{3,8})"?\s*$/);
    if (!m) continue;
    const [, key, hex] = m;
    if (!occurrences.has(key)) { occurrences.set(key, []); order.push(key); }
    occurrences.get(key).push(hex.toUpperCase());
  }

  const duplicates = order.filter(k => occurrences.get(k).length > 1);
  const pick = n => {
    const out = {};
    for (const k of order) {
      const list = occurrences.get(k);
      if (list[n] !== undefined) out[k] = list[n];
    }
    return out;
  };
  const blocks = duplicates.length
    ? Math.max(...duplicates.map(k => occurrences.get(k).length))
    : 1;

  return { colors: pick(0), colorsDark: blocks > 1 ? pick(1) : {}, duplicates, blocks };
}

function parseFontFamilies(fm) {
  const out = [];
  const re = /fontFamily:\s*"?([^"\n]+?)"?\s*$/gm;
  let m;
  while ((m = re.exec(fm)) !== null) {
    const first = m[1].split(',')[0].trim();
    if (first && !out.includes(first)) out.push(first);
  }
  return out;
}

const CJK_HINT = /(Noto\s+(Sans|Serif)\s+(SC|TC|JP|KR|HK)|Source\s+Han|PingFang|Hiragino|Microsoft\s+YaHei|Heiti|SimHei|SimSun|Songti|Kaiti|FangSong|Yu\s+(Gothic|Mincho)|Meiryo|Malgun|LXGW|Zhi\s?Mang|Alibaba\s+PuHui|HarmonyOS\s+Sans)/i;
const GENERIC = /^(sans-serif|serif|monospace|system-ui|cursive|fantasy|ui-\w+)$/i;

// ---------- 单份规范体检 ----------
export function analyze(filePath, kind) {
  const text = readFileSync(filePath, 'utf-8');
  const fm = splitFrontMatter(text);
  const { colors, colorsDark, duplicates, blocks } = parseColorBlock(fm);
  const families = parseFontFamilies(fm);

  const surface = colors['surface'] || colors['background'] || colors['canvas'] || null;
  const onSurface = colors['on-surface'] || colors['text'] || colors['foreground'] || null;
  const lum = surface ? relLuminance(surface) : null;

  // 明暗以 surface 相对亮度判定；0.5 是白/黑对比的中位。
  const isDark = lum === null ? null : lum < 0.5;

  const declaredFailPairs = [...text.matchAll(/\|\s*([^|]+?)\s*\|\s*`(#[0-9A-Fa-f]{6})`\s*\|\s*`(#[0-9A-Fa-f]{6})`\s*\|\s*[\d.]+:1\s*\|\s*FAIL/g)].length;

  const issues = [];
  if (!surface) issues.push('no-surface-token');
  if (duplicates.length) issues.push(`multi-theme-frontmatter:${duplicates.join('+')}`);
  const realFonts = families.filter(f => !GENERIC.test(f));
  if (realFonts.length === 0) issues.push('no-declared-font-family');
  if (!realFonts.some(f => CJK_HINT.test(f))) issues.push('no-cjk-font');
  if (onSurface && surface) {
    const cr = contrastRatio(onSurface, surface);
    if (cr !== null && cr < 4.5) issues.push(`text-contrast-${cr.toFixed(2)}`);
  }
  if (declaredFailPairs > 0) issues.push(`declared-fail-pairs:${declaredFailPairs}`);

  const zhMatch = text.match(/^#\s+(.+)$/gm)?.slice(1).find(l => /[\u4e00-\u9fff]/.test(l));

  const normalizedPath = filePath.replace(/\\/g, '/');
  const assetsIndex = normalizedPath.indexOf('assets/');

  return {
    id: filePath.split(/[/\\]/).pop().replace(/-DESIGN\.md$/, ''),
    kind,
    file: assetsIndex !== -1 ? normalizedPath.slice(assetsIndex) : normalizedPath,
    name: (text.match(/^#\s*Design System:\s*(.+)$/m) || [, 'Unknown'])[1].trim(),
    name_zh: zhMatch ? zhMatch.replace(/^#\s+/, '').trim() : null,
    surface,
    on_surface: onSurface,
    is_dark: isDark,
    // frontmatter 是否把亮/暗两套叠在一起（blocks>1）。true 时 colors 取第 1 块。
    multi_theme: blocks > 1,
    theme_blocks: blocks,
    colors,
    colors_dark: colorsDark,
    fonts: families,
    cjk_font: realFonts.some(f => CJK_HINT.test(f)),
    rounded: [...fm.matchAll(/^\s{2}([a-z0-9-]+):\s*"?([\d.]+px)"?\s*$/gm)].map(m => `${m[1]}=${m[2]}`),
    issues,
  };
}

function walk() {
  const entries = [];
  for (const [dir, kind] of [['styles', 'style'], ['masters', 'method']]) {
    const abs = join(SPEC_ROOT, dir);
    for (const f of readdirSync(abs).filter(x => x.endsWith('-DESIGN.md')).sort()) {
      entries.push(analyze(join(abs, f), kind));
    }
  }
  return entries;
}

function profileStyles(specs) {
  const config = JSON.parse(readFileSync(PROFILES, 'utf-8'));
  if (config.schema_version !== 1 || !config.groups || !config.overrides) {
    throw new Error('profiles.json must contain schema_version=1, groups, and overrides');
  }
  const styleIds = new Set(specs.filter(spec => spec.kind === 'style').map(spec => spec.id));
  const assignment = new Map();
  for (const [groupId, group] of Object.entries(config.groups)) {
    for (const id of group.ids || []) {
      if (!styleIds.has(id)) throw new Error(`profiles.json names unknown style ${id}`);
      if (assignment.has(id)) throw new Error(`profiles.json assigns ${id} more than once`);
      assignment.set(id, { groupId, group });
    }
  }
  const missing = [...styleIds].filter(id => !assignment.has(id));
  if (missing.length) throw new Error(`profiles.json is missing styles: ${missing.join(', ')}`);

  return specs.map(spec => {
    if (spec.kind !== 'style') {
      return {
        ...spec,
        role: 'optional-design-method',
        note: 'Methods may inform critique or craft; they are not grammar candidates.',
      };
    }
    const { groupId, group } = assignment.get(spec.id);
    const override = config.overrides[spec.id] || {};
    const semantic = { ...group.semantic, ...(override.semantic || {}) };
    const constraints = {
      ...group.constraints,
      color_schemes: spec.multi_theme ? ['light', 'dark'] : [spec.is_dark ? 'dark' : 'light'],
      ...(override.constraints || {}),
    };
    for (const dimension of config.dimensions || []) {
      if (!Array.isArray(semantic[dimension]) || semantic[dimension].length === 0) {
        throw new Error(`${spec.id} needs semantic.${dimension}`);
      }
    }
    return {
      ...spec,
      profile_group: groupId,
      semantic,
      constraints,
      strengths: override.strengths || group.strengths,
      tradeoffs: override.tradeoffs || group.tradeoffs,
      reject_conditions: override.reject_conditions || group.reject_conditions,
    };
  });
}

function build() {
  const specs = profileStyles(walk());
  const allFonts = new Map();
  for (const s of specs) for (const f of s.fonts) allFonts.set(f, (allFonts.get(f) || 0) + 1);

  const issueCount = {};
  for (const s of specs) for (const i of s.issues) {
    const k = i.split(':')[0];
    issueCount[k] = (issueCount[k] || 0) + 1;
  }

  return {
    schema_version: 2,
    source: {
      repo: 'https://github.com/xdx888999/xdx-lab-design-skill',
      vendored_at: 'assets/spec/',
    },
    selection_dimensions: JSON.parse(readFileSync(PROFILES, 'utf-8')).dimensions,
    counts: {
      styles: specs.filter(s => s.kind === 'style').length,
      methods: specs.filter(s => s.kind === 'method').length,
      dark: specs.filter(s => s.is_dark === true).length,
      light: specs.filter(s => s.is_dark === false).length,
      unknown_mode: specs.filter(s => s.is_dark === null).length,
      multi_theme: specs.filter(s => s.multi_theme).length,
      cjk_ready: specs.filter(s => s.cjk_font).length,
    },
    issue_counts: issueCount,
    font_frequency: [...allFonts.entries()].sort((a, b) => b[1] - a[1]).map(([family, count]) => ({ family, count })),
    specs,
  };
}

// 人类可读索引由 catalog.json 生成，避免与机读目录漂移。
function renderIndex(catalog) {
  const rows = catalog.specs.map(s => {
    const mode = s.is_dark === null ? '?' : s.is_dark ? '暗' : '亮';
    const cjk = s.cjk_font ? '✓' : '—';
    const warn = s.issues.length ? s.issues.map(i => i.split(':')[0]).join(' ') : '';
    if (s.kind === 'method') {
      return `| \`${s.id}\` | ${s.name_zh || s.name} | 方法 | — | — | — | — | 可选设计方法，不参与风格选择 | ${warn} |`;
    }
    const semantic = s.semantic;
    const task = semantic.tasks.join(' / ');
    const content = `${semantic.content_shapes.join(' / ')} · ${semantic.content_subjects.join(' / ')}`;
    const context = `${semantic.audiences.join(' / ')} · ${semantic.trust_postures.join(' / ')}`;
    const conditions = `${semantic.asset_conditions.join(' / ')} · ${semantic.interaction_intensities.join(' / ')} · ${semantic.primary_devices.join(' / ')}`;
    const tradeoff = `${s.strengths[0]} / 代价：${s.tradeoffs[0]}`;
    return `| \`${s.id}\` | ${s.name_zh || s.name} | 风格 | ${task} | ${content} | ${context} | ${conditions} | ${tradeoff}；拒绝：${s.reject_conditions[0]} | ${mode} CJK:${cjk} ${warn} |`;
  });

  return `# 规范库索引

> 本文件由 \`tools/catalog.mjs\` 从 \`catalog.json\` 生成，请勿手改。
> 规范正文来源记录见 [ATTRIBUTION.md](ATTRIBUTION.md)；本索引只负责选择与体检。
> 缺陷与已知限制见 [KNOWN-ISSUES.md](KNOWN-ISSUES.md)。

统计：风格 ${catalog.counts.styles} 份 · 可选方法 ${catalog.counts.methods} 份 · 暗色 ${catalog.counts.dark} · 亮色 ${catalog.counts.light} · 自带中文字体 ${catalog.counts.cjk_ready}/${catalog.specs.length} · 多主题叠加 ${catalog.counts.multi_theme}

风格条目提供选择器实际使用的任务、内容、受众、信任姿态、素材、交互和设备信息。行业名称不参与选择。

| spec_id | 名称 | 类型 | 任务 | 内容形态 / 主角 | 受众 / 信任 | 素材 / 交互 / 设备 | 强项 / 代价 / 拒绝条件 | 体检 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
${rows.join('\n')}

## 用法

- 先用 \`node tools/select.mjs --profile <profile.json> --limit 3 --kind style\` 选择；只读取最终选中的一个 \`styles/<id>.md\`。
- \`masters/\` 仅在需要特定设计方法时单独读取，不作为风格候选。
- 规范正文里 \`## 2. Color Palette & Roles\`、\`## 3. Typography Rules\`、\`## 4. Component Stylings\`、
  \`## 7. Do's and Don'ts\`、末节 \`Agent Prompt Guide\` 是执行时最需要照做的部分。
- 精选库没有的风格：读 \`knowledge-base.md\`（120+ 风格，约 800 行，**只在无精选文件时才读**）。
- 规范 → token：\`node tools/export.mjs --format css|tailwind|dtcg <规范路径>\`
- 产物符合性：\`node tools/check-output.mjs <产物.html> <规范路径>\`
`;
}

const catalog = build();
const serialized = JSON.stringify(catalog, null, 2) + '\n';
const indexMd = renderIndex(catalog);
const INDEX_OUT = join(SPEC_ROOT, 'INDEX.md');

if (CHECK) {
  const current = existsSync(OUT) ? readFileSync(OUT, 'utf-8') : '';
  const currentIndex = existsSync(INDEX_OUT) ? readFileSync(INDEX_OUT, 'utf-8') : '';
  if (current !== serialized || currentIndex !== indexMd) {
    console.error('catalog.json / INDEX.md 与规范库不一致。运行: node tools/catalog.mjs');
    process.exit(1);
  }
  console.log(`catalog.json 与 INDEX.md 均与规范库一致（${catalog.specs.length} 份资产）。`);
} else {
  writeFileSync(OUT, serialized);
  writeFileSync(INDEX_OUT, indexMd);
  const c = catalog.counts;
  console.log(`已写入 assets/spec/catalog.json 与 assets/spec/INDEX.md`);
  console.log(`  styles=${c.styles} methods=${c.methods} dark=${c.dark} light=${c.light} cjk_ready=${c.cjk_ready} multi_theme=${c.multi_theme}`);
  console.log('  体检发现:', Object.entries(catalog.issue_counts).map(([k, v]) => `${k}=${v}`).join(' ') || '无');
}
