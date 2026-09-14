#!/usr/bin/env node
// 静态规范预检：扫描 HTML、内联样式和本地链接 CSS，提示是否使用了所选
// DESIGN.md 的颜色与字体。它不运行浏览器，也不代表实际渲染或视觉验收。
import { existsSync, readFileSync } from 'fs';
import { dirname, resolve } from 'path';
import { parseDesignMd } from './lib/parser.mjs';

const GENERIC_COLOR_KEYWORDS = new Set([
  'black', 'white', 'gray', 'grey', 'red', 'blue', 'green', 'yellow',
  'orange', 'purple', 'pink', 'brown', 'cyan', 'magenta', 'lime',
  'navy', 'teal', 'maroon', 'olive', 'silver', 'gold',
  'lightgray', 'lightgrey', 'darkgray', 'darkgrey', 'dimgray', 'dimgrey',
  'lightblue', 'darkblue', 'lightgreen', 'darkgreen', 'lightpink',
]);

const [, , htmlPath, designPath] = process.argv;

if (!htmlPath || !designPath) {
  console.error('Usage: node tools/check-output.mjs <generated-output.html> <assets/spec/.../XX-DESIGN.md>');
  process.exit(1);
}

const html = readFileSync(htmlPath, 'utf-8');
const design = parseDesignMd(designPath);
const cssBlob = extractCss(html, htmlPath);

const findings = [];

// Rule 1: generic-color-keyword — 泛化色名代替精确 HEX
const colorPropRegex = /(?:^|[;{])\s*(color|background(?:-color)?|border(?:-color)?|fill|stroke)\s*:\s*([a-zA-Z-]+)\s*[;}]/gi;
const genericHits = new Map();
for (const m of cssBlob.matchAll(colorPropRegex)) {
  const value = m[2].toLowerCase();
  if (GENERIC_COLOR_KEYWORDS.has(value)) {
    genericHits.set(value, (genericHits.get(value) || 0) + 1);
  }
}
for (const [keyword, count] of genericHits) {
  findings.push({
    severity: 'warning',
    rule: 'generic-color-keyword',
    message: `Used generic CSS color keyword "${keyword}" (${count}x) instead of an exact HEX token from ${design.name}`,
  });
}

// Rule 2: unlisted-hex-color — 出现了 DESIGN.md token 列表里没有的 HEX
const tokenHexes = new Set(
  design.colors.map(c => c.hex).filter(Boolean).map(h => h.toUpperCase()),
);
const hexRegex = /#[0-9A-Fa-f]{3,8}\b/g;
const usedHexes = new Map();
for (const m of cssBlob.matchAll(hexRegex)) {
  const hex = normalizeHex(m[0]);
  if (!hex) continue;
  usedHexes.set(hex, (usedHexes.get(hex) || 0) + 1);
}
for (const [hex, count] of usedHexes) {
  if (!tokenHexes.has(hex)) {
    findings.push({
      severity: 'warning',
      rule: 'unlisted-hex-color',
      message: `HEX ${hex} (${count}x) is not declared in ${design.name}'s token list — confirm it's an intentional accent, not an ad-hoc guess`,
    });
  }
}

// Rule 3: missing-declared-font — 完全没用到 DESIGN.md 指定的任何字体
const declaredFamilies = new Set(
  [...design.typography.families, ...design.typography.scale]
    .map(f => f.family || f.fontFamily)
    .filter(Boolean)
    .map(f => f.toLowerCase()),
);
const fontFamilyRegex = /font-family\s*:\s*([^;}]+)/gi;
const usedFamilies = new Set();
for (const m of cssBlob.matchAll(fontFamilyRegex)) {
  const first = m[1].split(',')[0].replace(/['"]/g, '').trim().toLowerCase();
  if (first) usedFamilies.add(first);
}
const anyDeclaredUsed = [...declaredFamilies].some(f => usedFamilies.has(f));
if (declaredFamilies.size > 0 && !anyDeclaredUsed) {
  findings.push({
    severity: 'error',
    rule: 'missing-declared-font',
    message: `None of ${design.name}'s declared fonts (${[...declaredFamilies].join(', ')}) appear in the output; found instead: ${[...usedFamilies].join(', ') || '(none)'}`,
  });
}

// Rule 4: token-coverage — 有多少声明的 token 真的被用到（info，不影响退出码）
const usedTokenCount = [...tokenHexes].filter(h => usedHexes.has(h)).length;
findings.push({
  severity: 'info',
  rule: 'token-coverage',
  message: `${usedTokenCount}/${tokenHexes.size} declared color tokens actually used in the output`,
});

let errors = 0;
let warnings = 0;
let infos = 0;
console.log(`\nStatic conformity preflight (not rendered evidence)\n${htmlPath}\n  vs ${design.name} (${designPath}):`);
for (const f of findings) {
  const icon = f.severity === 'error' ? '✗' : f.severity === 'warning' ? '⚠' : 'ℹ';
  console.log(`  ${icon} [${f.rule}] ${f.message}`);
  if (f.severity === 'error') errors++;
  else if (f.severity === 'warning') warnings++;
  else infos++;
}
console.log(`\n━━━ Summary ━━━`);
console.log(`Errors: ${errors} | Warnings: ${warnings} | Info: ${infos}`);
if (errors > 0) process.exit(1);

function extractCss(html, sourcePath) {
  const parts = [];
  const styleBlockRegex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
  for (const m of html.matchAll(styleBlockRegex)) parts.push(m[1]);
  const attrRegex = /\sstyle\s*=\s*"([^"]*)"/gi;
  for (const m of html.matchAll(attrRegex)) parts.push(m[1] + ';');
  for (const match of html.matchAll(/<link\b[^>]*>/gi)) {
    const tag = match[0];
    const rel = attribute(tag, 'rel').toLowerCase().split(/\s+/);
    const href = attribute(tag, 'href');
    if (!rel.includes('stylesheet') || !href || /^(?:[a-z]+:|\/\/)/i.test(href)) continue;
    const local = resolve(dirname(sourcePath), decodeURIComponent(href.split(/[?#]/)[0]));
    if (existsSync(local)) parts.push(readFileSync(local, 'utf8'));
  }
  return parts.join('\n');
}

function attribute(tag, name) {
  const match = tag.match(new RegExp(`\\s${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i'));
  return match ? (match[1] ?? match[2] ?? match[3] ?? '') : '';
}

function normalizeHex(hex) {
  const h = hex.slice(1);
  if (h.length === 3) return '#' + h.split('').map(c => c + c).join('').toUpperCase();
  if (h.length === 6) return '#' + h.toUpperCase();
  if (h.length === 8) return '#' + h.slice(0, 6).toUpperCase();
  return null;
}
