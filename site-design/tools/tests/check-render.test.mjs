import test from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const TOOLS = join(dirname(fileURLToPath(import.meta.url)), '..');
const FIXTURES = join(TOOLS, 'tests', 'fixtures');

function runEntry(entry, contract) {
  const output = mkdtempSync(join(tmpdir(), 'render-check-'));
  const args = [join(TOOLS, 'check-render.mjs'), '--entry', entry, '--output', output];
  if (contract) args.push('--contract', contract);
  return spawnSync(process.execPath, args, { encoding: 'utf8', timeout: 120_000 });
}

function run(fixture, contract) {
  return runEntry(
    join(FIXTURES, fixture, 'index.html'),
    contract ? join(FIXTURES, fixture, contract) : null,
  );
}

test('positive control proves linked CSS, states, core task and reopen checks can pass', { timeout: 120_000 }, () => {
  const result = run('render-good', 'contract.json');
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const report = JSON.parse(result.stdout);
  assert.equal(report.status, 'passed');
  assert.equal(report.viewports.length, 2);
  assert.equal(report.contract.core_task.status, 'passed');
  assert.equal(report.contract.reopen.status, 'passed');
  assert.ok(report.contract.state_probes.every(probe => probe.status === 'passed'));
  assert.ok(report.viewports.every(viewport => viewport.screenshot));
});

test('negative control proves rendered probes fail on linked-CSS defects', { timeout: 120_000 }, () => {
  const result = run('render-bad');
  assert.equal(result.status, 1, result.stderr || result.stdout);
  const report = JSON.parse(result.stdout);
  assert.equal(report.status, 'failed');
  const codes = report.viewports.flatMap(viewport => viewport.issues.map(issue => issue.code));
  assert.ok(codes.includes('low-text-contrast'));
  assert.ok(codes.includes('horizontal-overflow'));
  assert.ok(codes.includes('small-touch-target'));
  assert.ok(codes.includes('missing-cjk-fallback'));
});

test('reopen control rejects state that survives reload but not closing the page', { timeout: 120_000 }, () => {
  const folder = mkdtempSync(join(tmpdir(), 'render-session-only-'));
  cpSync(join(FIXTURES, 'render-good'), folder, { recursive: true });
  const app = join(folder, 'app.js');
  writeFileSync(app, readFileSync(app, 'utf8').replaceAll('localStorage', 'sessionStorage'));

  const result = runEntry(join(folder, 'index.html'), join(folder, 'contract.json'));

  assert.equal(result.status, 1, result.stderr || result.stdout);
  const report = JSON.parse(result.stdout);
  assert.equal(report.contract.reopen.status, 'failed');
});

test('contract control rejects unsupported actions and empty step lists', { timeout: 120_000 }, () => {
  const folder = mkdtempSync(join(tmpdir(), 'render-invalid-contract-'));
  const unknown = join(folder, 'unknown.json');
  const empty = join(folder, 'empty.json');
  writeFileSync(unknown, JSON.stringify({
    core_task: { name: 'invalid action', steps: [{ action: 'launch', selector: '#save' }] },
  }));
  writeFileSync(empty, JSON.stringify({
    core_task: { name: 'empty task', steps: [] },
    reopen: { name: 'empty reopen', before: [], after: [] },
  }));

  for (const contract of [unknown, empty]) {
    const result = runEntry(join(FIXTURES, 'render-good', 'index.html'), contract);
    assert.equal(result.status, 1, result.stderr || result.stdout);
    assert.equal(JSON.parse(result.stdout).contract.core_task.status, 'failed');
  }
});
