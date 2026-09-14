import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const catalog = JSON.parse(readFileSync(join(ROOT, 'assets/spec/catalog.json'), 'utf8'));

test('every style exposes the semantic dimensions used by selection', () => {
  const fields = [
    'tasks', 'content_shapes', 'content_subjects', 'audiences',
    'trust_postures', 'asset_conditions', 'interaction_intensities',
    'primary_devices',
  ];
  const styles = catalog.specs.filter(spec => spec.kind === 'style');
  assert.equal(styles.length, 50);
  for (const style of styles) {
    for (const field of fields) {
      assert.ok(Array.isArray(style.semantic?.[field]) && style.semantic[field].length > 0,
        `${style.id} needs semantic.${field}`);
    }
    assert.ok(style.constraints?.visual_risk, `${style.id} needs visual risk`);
    assert.ok(Array.isArray(style.strengths) && style.strengths.length > 0);
    assert.ok(Array.isArray(style.tradeoffs) && style.tradeoffs.length > 0);
    assert.ok(Array.isArray(style.reject_conditions) && style.reject_conditions.length > 0);
  }
});

test('master references are methods rather than style candidates', () => {
  assert.equal(catalog.specs.filter(spec => spec.kind === 'method').length, 20);
  assert.equal(catalog.specs.some(spec => spec.kind === 'master'), false);
});
