import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const repoRoot = fileURLToPath(new URL('../..', import.meta.url));

const FIXTURE_DESIGN_MD = `---
version: alpha
name: "Fixture Style"
colors:
  surface: "#FAFAF8"
  on-surface: "#111111"
  primary: "#B8973A"
  on-primary: "#FFFFFF"
typography:
  heading:
    fontFamily: "Playfair Display, serif"
    fontSize: 48px
    fontWeight: 400
  body:
    fontFamily: "Jost, sans-serif"
    fontSize: 15px
    fontWeight: 300
rounded:
  none: 0px
---

# Design System: Fixture Style

## 1. Visual Theme
测试用规范。

## 2. Color Palette
- **Surface** (\`#FAFAF8\`): background
- **On Surface** (\`#111111\`): text
- **Primary** (\`#B8973A\`): accent

## 3. Typography
- **Heading**: \`Playfair Display\`
- **Body**: \`Jost\`

## 4. Component
Button uses primary color.

## 5. Do's and Don'ts
Do keep it minimal.
`;

async function withFixtures(run) {
  const tempDir = await mkdtemp(join(tmpdir(), 'design-skill-check-output-'));
  const designPath = join(tempDir, 'fixture-DESIGN.md');
  await writeFile(designPath, FIXTURE_DESIGN_MD);
  try {
    await run(tempDir, designPath);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
}

function runCheck(htmlPath, designPath) {
  return spawnSync(process.execPath, ['tools/check-output.mjs', htmlPath, designPath], {
    cwd: repoRoot,
    encoding: 'utf8',
  });
}

test('check-output 对严格使用 token 的产物报告 0 warning', async () => {
  await withFixtures(async (tempDir, designPath) => {
    const htmlPath = join(tempDir, 'clean.html');
    await writeFile(htmlPath, `<!DOCTYPE html><html><head><style>
      body { background: #FAFAF8; color: #111111; font-family: "Jost", sans-serif; }
      h1 { color: #B8973A; font-family: "Playfair Display", serif; }
    </style></head><body><h1>Title</h1></body></html>`);

    const result = runCheck(htmlPath, designPath);

    assert.equal(result.status, 0, result.stdout);
    assert.match(result.stdout, /Errors: 0 \| Warnings: 0/);
    assert.match(result.stdout, /\[token-coverage\] 3\/3 declared color tokens actually used/);
  });
});

test('check-output 检测泛化色名和未声明的 HEX', async () => {
  await withFixtures(async (tempDir, designPath) => {
    const htmlPath = join(tempDir, 'generic.html');
    await writeFile(htmlPath, `<!DOCTYPE html><html><head><style>
      body { background: gray; color: #333333; font-family: "Jost", sans-serif; }
      .card { border-color: blue; }
    </style></head><body>test</body></html>`);

    const result = runCheck(htmlPath, designPath);

    assert.equal(result.status, 0, result.stdout);
    assert.match(result.stdout, /\[generic-color-keyword\].*"gray"/);
    assert.match(result.stdout, /\[generic-color-keyword\].*"blue"/);
    assert.match(result.stdout, /\[unlisted-hex-color\].*#333333/);
  });
});

test('check-output 在完全没用到声明字体时报 error 并返回非 0 退出码', async () => {
  await withFixtures(async (tempDir, designPath) => {
    const htmlPath = join(tempDir, 'wrong-font.html');
    await writeFile(htmlPath, `<!DOCTYPE html><html><head><style>
      body { background: #FAFAF8; color: #111111; font-family: Arial, sans-serif; }
    </style></head><body>test</body></html>`);

    const result = runCheck(htmlPath, designPath);

    assert.equal(result.status, 1);
    assert.match(result.stdout, /\[missing-declared-font\]/);
  });
});

test('check-output 对同一 HEX 的重复出现只报告一次并统计次数', async () => {
  await withFixtures(async (tempDir, designPath) => {
    const htmlPath = join(tempDir, 'repeated.html');
    await writeFile(htmlPath, `<!DOCTYPE html><html><head><style>
      body { font-family: "Jost", sans-serif; }
      .a { color: #FF00AA; }
      .b { background: #ff00aa; }
    </style></head><body>test</body></html>`);

    const result = runCheck(htmlPath, designPath);

    const matches = [...result.stdout.matchAll(/#FF00AA/gi)];
    assert.equal(matches.length, 1, result.stdout);
    assert.match(result.stdout, /#FF00AA \(2x\)/i);
  });
});

test('check-output 静态预检会读取本地链接样式表', async () => {
  await withFixtures(async (tempDir, designPath) => {
    const htmlPath = join(tempDir, 'linked.html');
    await writeFile(htmlPath, '<!doctype html><html><head><link rel="stylesheet" href="style.css"></head><body>test</body></html>');
    await writeFile(join(tempDir, 'style.css'), `
      body { background: #FAFAF8; color: #111111; font-family: "Jost", sans-serif; }
      h1 { color: #B8973A; font-family: "Playfair Display", serif; }
    `);

    const result = runCheck(htmlPath, designPath);

    assert.equal(result.status, 0, result.stdout);
    assert.match(result.stdout, /Static conformity preflight/);
    assert.match(result.stdout, /Errors: 0 \| Warnings: 0/);
  });
});
