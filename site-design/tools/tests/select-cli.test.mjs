import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const TOOLS = join(dirname(fileURLToPath(import.meta.url)), '..');

function run(profile, ...args) {
  const folder = mkdtempSync(join(tmpdir(), 'site-select-'));
  const path = join(folder, 'profile.json');
  writeFileSync(path, JSON.stringify(profile));
  return spawnSync(process.execPath, [join(TOOLS, 'select.mjs'), '--profile', path, ...args], {
    encoding: 'utf8',
  });
}

test('CLI selects no more than the requested number of real catalog styles', () => {
  const result = run({
    task: 'analyze',
    content_shape: 'dense-data',
    content_subject: 'financial-data',
    audience: 'professional',
    trust_posture: 'technical',
    asset_conditions: 'data-available',
    interaction_intensity: 'high',
    primary_device: 'desktop',
    constraints: { max_visual_risk: 'medium' },
  }, '--kind', 'style', '--limit', '2');
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.status, 'matched');
  assert.ok(output.candidates.length > 0 && output.candidates.length <= 2);
  assert.ok(output.candidates.every(candidate => candidate.kind === 'style'));
});

test('CLI fails closed for an industry label without task evidence', () => {
  const result = run({ industry: 'finance' }, '--kind', 'style');
  assert.equal(result.status, 2);
  const output = JSON.parse(result.stdout);
  assert.equal(output.status, 'needs_profile');
  assert.deepEqual(output.ignored, ['industry']);
});

test('CLI can select implementation templates without treating them as visual directions', () => {
  const result = run({
    task: 'transact',
    content_shape: 'form-flow',
    content_subject: 'request',
    audience: 'general',
    trust_posture: 'practical',
    asset_conditions: 'none-available',
    interaction_intensity: 'medium',
    primary_device: 'mobile',
  }, '--kind', 'template');
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.candidates[0].id, 'form');
  assert.ok(output.candidates.every(candidate => candidate.kind === 'template'));
});
