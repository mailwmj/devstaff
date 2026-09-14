import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const TOOLS = join(dirname(fileURLToPath(import.meta.url)), '..');
const FIXTURES = join(TOOLS, 'tests', 'fixtures');

function run(fixture, contract) {
  const output = mkdtempSync(join(tmpdir(), 'render-check-'));
  const args = [join(TOOLS, 'check-render.mjs'), '--entry', join(FIXTURES, fixture, 'index.html'), '--output', output];
  if (contract) args.push('--contract', join(FIXTURES, fixture, contract));
  return spawnSync(process.execPath, args, { encoding: 'utf8', timeout: 120_000 });
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
