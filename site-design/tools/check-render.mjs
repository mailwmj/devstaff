#!/usr/bin/env node
import { execFile } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync, unlinkSync } from 'node:fs';
import { createServer } from 'node:http';
import { homedir } from 'node:os';
import { basename, dirname, extname, join, relative, resolve } from 'node:path';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'mobile', width: 390, height: 844 },
];

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--entry') args.entry = argv[++index];
    else if (token === '--contract') args.contract = argv[++index];
    else if (token === '--output') args.output = argv[++index];
    else throw new Error(`Unknown argument: ${token}`);
  }
  if (!args.entry) throw new Error('Usage: node tools/check-render.mjs --entry <URL|HTML> [--contract contract.json] [--output evidence-dir]');
  return args;
}

function mime(path) {
  return ({
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
    '.woff2': 'font/woff2',
  })[extname(path).toLowerCase()] || 'application/octet-stream';
}

async function serveEntry(entry) {
  if (/^https?:\/\//i.test(entry)) return { url: entry, close: async () => {} };
  const file = resolve(entry);
  if (!existsSync(file) || !['.html', '.htm'].includes(extname(file).toLowerCase())) {
    throw new Error('--entry must be an HTTP(S) URL or an existing HTML file');
  }
  const root = dirname(file);
  const server = createServer((request, response) => {
    try {
      const raw = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      const requested = resolve(root, raw === '/' ? basename(file) : `.${raw}`);
      if (relative(root, requested).startsWith('..') || !existsSync(requested)) {
        response.writeHead(404).end('Not found');
        return;
      }
      response.writeHead(200, { 'Content-Type': mime(requested) });
      response.end(readFileSync(requested));
    } catch {
      response.writeHead(400).end('Bad request');
    }
  });
  await new Promise((accept, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', accept);
  });
  const address = server.address();
  return {
    url: `http://127.0.0.1:${address.port}/${encodeURIComponent(basename(file))}`,
    close: () => new Promise(accept => server.close(accept)),
  };
}

function cliCommand() {
  const configured = process.env.PWCLI;
  const bundled = join(homedir(), '.codex', 'skills', 'playwright', 'scripts', 'playwright_cli.sh');
  if (configured && existsSync(configured)) return { command: configured, prefix: [] };
  if (existsSync(bundled)) return { command: bundled, prefix: [] };
  const command = process.platform === 'win32' ? 'npx.cmd' : 'npx';
  return { command, prefix: ['--yes', '--package', '@playwright/cli', 'playwright-cli'] };
}

async function runCli(session, args, cwd) {
  const cli = cliCommand();
  const isWin = process.platform === 'win32' && (cli.command === 'npx' || cli.command === 'npx.cmd');
  let tempScriptFile = null;
  let finalArgs = args;
  if (args[0] === 'run-code' && typeof args[1] === 'string') {
    const tmpDir = join(homedir(), '.codex', 'tmp');
    mkdirSync(tmpDir, { recursive: true });
    tempScriptFile = join(tmpDir, `pw-code-${session}-${Date.now()}-${Math.random().toString(36).slice(2)}.js`);
    writeFileSync(tempScriptFile, args[1], 'utf8');
    finalArgs = ['run-code', '--filename', tempScriptFile];
  }
  try {
    const { stdout, stderr } = await execFileAsync(
      cli.command,
      [...cli.prefix, `-s=${session}`, '--json', ...finalArgs],
      { cwd, maxBuffer: 16 * 1024 * 1024, timeout: 120_000, shell: isWin },
    );
    let output;
    try {
      output = JSON.parse(stdout);
    } catch {
      throw new Error(`Browser command returned invalid JSON: ${stderr || stdout}`);
    }
    if (output.isError || output.error) throw new Error(output.error || stderr || 'Browser command failed');
    return output;
  } finally {
    if (tempScriptFile && existsSync(tempScriptFile)) {
      try { unlinkSync(tempScriptFile); } catch {}
    }
  }
}

const DIAGNOSTICS = String.raw`async page => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.evaluate(() => document.fonts.ready);
  const base = await page.evaluate(() => {
    const issues = [];
    const seen = new Set();
    const add = (code, severity, selector, message, detail = {}) => {
      const key = code + ':' + selector;
      if (!seen.has(key)) { seen.add(key); issues.push({ code, severity, selector, message, ...detail }); }
    };
    const selector = element => {
      if (element.id) return '#' + CSS.escape(element.id);
      const parent = element.parentElement;
      if (!parent) return element.tagName.toLowerCase();
      const peers = [...parent.children].filter(node => node.tagName === element.tagName);
      return element.tagName.toLowerCase() + (peers.length > 1 ? ':nth-of-type(' + (peers.indexOf(element) + 1) + ')' : '');
    };
    const visible = element => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return !element.hidden && style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && rect.width > 0 && rect.height > 0;
    };
    const rgba = value => {
      const match = value.match(/rgba?\(([^)]+)\)/);
      if (!match) return null;
      const parts = match[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
      return parts.length >= 3 && parts.slice(0, 3).every(Number.isFinite)
        ? { r: parts[0], g: parts[1], b: parts[2], a: Number.isFinite(parts[3]) ? parts[3] : 1 }
        : null;
    };
    const background = element => {
      let current = element;
      while (current) {
        const style = getComputedStyle(current);
        if (style.backgroundImage !== 'none') return null;
        const color = rgba(style.backgroundColor);
        if (color && color.a >= 0.98) return color;
        current = current.parentElement;
      }
      return { r: 255, g: 255, b: 255, a: 1 };
    };
    const luminance = color => {
      const channels = [color.r, color.g, color.b].map(value => {
        const channel = value / 255;
        return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    };
    const contrast = (one, two) => {
      const a = luminance(one), b = luminance(two);
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    };

    const root = document.documentElement;
    if (root.scrollWidth > root.clientWidth + 1) {
      add('horizontal-overflow', 'error', 'html', 'Document is wider than the viewport', { scroll_width: root.scrollWidth, viewport_width: root.clientWidth });
    }

    const all = [...document.body.querySelectorAll('*')];
    for (const element of all) {
      if (!visible(element)) continue;
      const ownText = [...element.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
      if (ownText) {
        const style = getComputedStyle(element);
        const foreground = rgba(style.color);
        const behind = background(element);
        if (foreground && behind) {
          const ratio = contrast(foreground, behind);
          const size = parseFloat(style.fontSize);
          const weight = Number(style.fontWeight) || 400;
          const large = size >= 24 || (size >= 18.66 && weight >= 700);
          const minimum = large ? 3 : 4.5;
          if (ratio < minimum) add('low-text-contrast', 'error', selector(element), 'Rendered text contrast is below its WCAG threshold', { ratio: Number(ratio.toFixed(2)), minimum });
        }
        if (/[\u3400-\u9fff]/.test(element.textContent)) {
          const family = style.fontFamily;
          if (!/(PingFang|Hiragino|Microsoft YaHei|Noto Sans SC|Noto Serif SC|Source Han|SimHei|SimSun|Songti|Kaiti|FangSong|system-ui|sans-serif|serif)/i.test(family)) {
            add('missing-cjk-fallback', 'error', selector(element), 'Chinese text has no declared CJK or generic fallback', { font_family: family });
          }
        }
      }
    }

    const interactive = [...document.querySelectorAll('button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [role="button"]')].filter(visible);
    for (const element of interactive) {
      const label = element.matches('input[type="checkbox"], input[type="radio"], input[type="file"]')
        ? element.closest('label')
        : null;
      const rect = label && visible(label) ? label.getBoundingClientRect() : element.getBoundingClientRect();
      if (rect.width < 44 || rect.height < 44) {
        add('small-touch-target', 'error', selector(element), 'Interactive target is smaller than 44 by 44 CSS pixels', { width: Number(rect.width.toFixed(1)), height: Number(rect.height.toFixed(1)) });
      }
    }

    for (const image of [...document.images].filter(visible)) {
      if (!image.complete || image.naturalWidth === 0) add('image-not-loaded', 'error', selector(image), 'Image did not load');
      if (!image.hasAttribute('alt')) add('missing-image-alt', 'error', selector(image), 'Image has no alt attribute');
      const style = getComputedStyle(image);
      if (style.objectFit === 'cover' && image.naturalWidth && image.naturalHeight) {
        const natural = image.naturalWidth / image.naturalHeight;
        const rendered = image.clientWidth / image.clientHeight;
        const crop = Math.max(natural / rendered, rendered / natural);
        if (crop > 1.8) add('heavy-image-crop', 'warning', selector(image), 'Image cover crop removes a large share of one dimension', { crop_factor: Number(crop.toFixed(2)) });
      }
    }

    const animated = all.filter(element => {
      if (!visible(element)) return false;
      const style = getComputedStyle(element);
      const durations = (style.animationDuration + ',' + style.transitionDuration).match(/[\d.]+m?s/g) || [];
      return durations.some(value => value.endsWith('ms') ? parseFloat(value) > 100 : parseFloat(value) > 0.1);
    });
    if (animated.length) add('reduced-motion-not-honored', 'error', selector(animated[0]), 'Long animation or transition remains when reduced motion is requested', { count: animated.length });

    return {
      title: document.title,
      url: location.href,
      document_size: { width: root.scrollWidth, height: root.scrollHeight },
      fonts_status: document.fonts.status,
      linked_stylesheets: [...document.styleSheets].filter(sheet => sheet.href).map(sheet => sheet.href),
      state_inventory: {
        interactive: interactive.length,
        disabled: document.querySelectorAll(':disabled').length,
        visible_errors: [...document.querySelectorAll('[role="alert"], [aria-invalid="true"]')].filter(visible).length,
        visible_loading: [...document.querySelectorAll('[aria-busy="true"], [data-state="loading"]')].filter(visible).length,
      },
      issues,
    };
  });

  const focusIssues = [];
  const count = await page.locator('button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [role="button"]').count();
  for (let index = 0; index < Math.min(count, 30); index++) {
    const locator = page.locator('button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [role="button"]').nth(index);
    if (!(await locator.isVisible())) continue;
    await locator.focus();
    const result = await locator.evaluate(element => {
      const style = getComputedStyle(element);
      return {
        selector: element.id ? '#' + CSS.escape(element.id) : element.tagName.toLowerCase(),
        visible: element.matches(':focus-visible'),
        outline: style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0,
        shadow: style.boxShadow !== 'none',
      };
    });
    if (!result.visible || (!result.outline && !result.shadow)) focusIssues.push({ code: 'missing-focus-indicator', severity: 'error', selector: result.selector, message: 'Keyboard focus has no visible outline or shadow' });
  }
  base.issues.push(...focusIssues);
  return base;
}`;

function contractRunner(contract) {
  return `async page => {
    const contract = ${JSON.stringify(contract)};
    const result = { core_task: { status: 'not_run', steps: [] }, state_probes: [], reopen: { status: 'not_run', steps: [] } };
    const styleSignature = async locator => locator.evaluate(element => {
      const style = getComputedStyle(element);
      return [style.color, style.backgroundColor, style.borderColor, style.boxShadow, style.transform, style.textDecorationLine, style.opacity].join('|');
    });
    const runSteps = async steps => {
      const rows = [];
      for (const step of steps || []) {
        try {
          const locator = step.selector ? page.locator(step.selector).first() : null;
          if (step.action === 'fill') await locator.fill(String(step.value ?? ''));
          else if (step.action === 'click') await locator.click();
          else if (step.action === 'click_confirm') {
            await page.evaluate(() => {
              window.__renderCheckConfirmCalls = 0;
              window.confirm = () => { window.__renderCheckConfirmCalls += 1; return true; };
            });
            await locator.click();
            const calls = await page.evaluate(() => window.__renderCheckConfirmCalls);
            if (!calls) throw new Error('expected the action to request confirmation');
          }
          else if (step.action === 'check') await locator.check();
          else if (step.action === 'uncheck') await locator.uncheck();
          else if (step.action === 'select') await locator.selectOption(String(step.value));
          else if (step.action === 'hover') await locator.hover();
          else if (step.action === 'press') await page.keyboard.press(String(step.value));
          else if (step.action === 'wait') await page.waitForTimeout(Number(step.value));
          else if (step.action === 'reload') await page.reload({ waitUntil: 'networkidle' });
          else if (step.assert === 'visible' && !(await locator.isVisible())) throw new Error('expected visible');
          else if (step.assert === 'hidden' && await locator.isVisible()) throw new Error('expected hidden');
          else if (step.assert === 'enabled' && !(await locator.isEnabled())) throw new Error('expected enabled');
          else if (step.assert === 'disabled' && !(await locator.isDisabled())) throw new Error('expected disabled');
          else if (step.assert === 'text' && !(await locator.textContent() || '').includes(String(step.value))) throw new Error('expected text: ' + step.value);
          else if (step.assert === 'value' && await locator.inputValue() !== String(step.value)) throw new Error('expected value: ' + step.value);
          else if (step.assert === 'count' && await page.locator(step.selector).count() !== Number(step.value)) throw new Error('expected count: ' + step.value);
          else if (step.assert === 'url' && !page.url().includes(String(step.value))) throw new Error('expected URL containing: ' + step.value);
          else if (!step.action && !step.assert) throw new Error('step needs action or assert');
          rows.push({ ...step, status: 'passed' });
        } catch (error) {
          rows.push({ ...step, status: 'failed', error: error.message });
          return { status: 'failed', steps: rows };
        }
      }
      return { status: 'passed', steps: rows };
    };

    if (contract.core_task) {
      result.core_task = { name: contract.core_task.name || 'core task', ...(await runSteps(contract.core_task.steps)) };
    }
    for (const probe of contract.state_probes || []) {
      const row = { name: probe.name, kind: probe.kind, selector: probe.selector };
      try {
        const locator = page.locator(probe.selector).first();
        if (probe.kind === 'focus') {
          await page.evaluate(() => document.activeElement?.blur());
          const tabStops = await page.locator('button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [role="button"]').count();
          for (let index = 0; index <= tabStops; index++) {
            await page.keyboard.press('Tab');
            if (await locator.evaluate(element => document.activeElement === element)) break;
          }
          const state = await locator.evaluate(element => {
            const style = getComputedStyle(element);
            return element.matches(':focus-visible') && ((style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== 'none');
          });
          if (!state) throw new Error('focus indicator is not visible');
        } else if (probe.kind === 'hover') {
          await page.mouse.move(0, 0);
          const before = await styleSignature(locator); await locator.hover(); const after = await styleSignature(locator);
          if (before === after) throw new Error('hover has no visible style change');
        } else if (probe.kind === 'disabled') {
          if (!(await locator.isDisabled())) throw new Error('element is not disabled');
        } else if (probe.kind === 'error' || probe.kind === 'loading') {
          const visible = await locator.isVisible();
          if ((probe.expected || 'visible') === 'hidden' ? visible : !visible) throw new Error('visibility differs from expected ' + (probe.expected || 'visible'));
        } else throw new Error('unknown state probe kind');
        row.status = 'passed';
      } catch (error) { row.status = 'failed'; row.error = error.message; }
      result.state_probes.push(row);
    }
    if (contract.reopen) {
      const before = await runSteps(contract.reopen.before);
      if (before.status === 'passed') await page.reload({ waitUntil: 'networkidle' });
      const after = before.status === 'passed' ? await runSteps(contract.reopen.after) : { status: 'not_run', steps: [] };
      result.reopen = {
        name: contract.reopen.name || 'reopen',
        status: before.status === 'passed' && after.status === 'passed' ? 'passed' : 'failed',
        steps: [...before.steps, ...after.steps],
      };
    }
    return result;
  }`;
}

function parseRunCode(output) {
  if (typeof output.result !== 'string') throw new Error('Browser evaluation returned no result');
  return JSON.parse(output.result);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const contract = args.contract ? JSON.parse(readFileSync(resolve(args.contract), 'utf8')) : null;
  const outputDirectory = resolve(args.output || join(process.cwd(), 'output', 'render-check'));
  mkdirSync(outputDirectory, { recursive: true });
  const served = await serveEntry(args.entry);
  const session = `site-render-${process.pid}-${Date.now()}`;
  const report = {
    schema_version: 1,
    kind: 'render',
    entry: args.entry,
    created_at: new Date().toISOString(),
    browser: 'chromium via playwright-cli',
    viewports: [],
    contract: {
      core_task: { status: 'not_run', steps: [] },
      state_probes: [],
      reopen: { status: 'not_run', steps: [] },
    },
    limits: ['Composition, project specificity, and visual-direction quality still require independent visual judgment'],
  };
  try {
    await runCli(session, ['open', served.url], outputDirectory);
    for (const viewport of VIEWPORTS) {
      await runCli(session, ['resize', String(viewport.width), String(viewport.height)], outputDirectory);
      await runCli(session, ['goto', served.url], outputDirectory);
      const diagnostics = parseRunCode(await runCli(session, ['run-code', DIAGNOSTICS], outputDirectory));
      const screenshot = join(outputDirectory, `${viewport.name}.png`);
      await runCli(session, ['screenshot', '--filename', screenshot, '--full-page'], outputDirectory);
      report.viewports.push({ ...viewport, ...diagnostics, screenshot: existsSync(screenshot) ? screenshot : null });
    }
    if (contract) {
      await runCli(session, ['resize', '1280', '800'], outputDirectory);
      await runCli(session, ['goto', served.url], outputDirectory);
      report.contract = parseRunCode(await runCli(session, ['run-code', contractRunner(contract)], outputDirectory));
    }
  } finally {
    try { await runCli(session, ['close'], outputDirectory); } catch {}
    await served.close();
  }
  const renderFailed = report.viewports.some(viewport => viewport.issues.some(issue => issue.severity === 'error'));
  const contractFailed = report.contract.core_task.status === 'failed'
    || report.contract.reopen.status === 'failed'
    || report.contract.state_probes.some(probe => probe.status === 'failed');
  report.status = renderFailed || contractFailed ? 'failed' : 'passed';
  console.log(JSON.stringify(report, null, 2));
  if (report.status === 'failed') process.exitCode = 1;
}

main().catch(error => {
  console.error(JSON.stringify({ error: error.message }));
  process.exitCode = 2;
});
