import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

import { prepareDesign, DESIGN_PACKET_MAX_BYTES } from '../lib/design-packet.mjs';

const style = index => ({
  id: `style-${index}`,
  kind: 'style',
  name: `Style ${index}`,
  file: `style-${index}.md`,
  semantic: {
    tasks: ['read'],
    content_shapes: ['long-form'],
    content_subjects: ['text'],
    audiences: ['general'],
    trust_postures: ['human'],
    asset_conditions: ['none-available'],
    interaction_intensities: ['low'],
    primary_devices: ['mobile'],
  },
  constraints: { color_schemes: ['light'], requires_images: false, visual_risk: 'low' },
  strengths: ['clear reading'],
  tradeoffs: ['quiet'],
  reject_conditions: ['dense operations'],
});

const input = {
  project: { name: '社区口述史', language: 'zh-CN', ignored: 'drop me' },
  facts: [{ source: 'brief', value: '长辈会在手机上阅读长篇访谈', evidence: 'measured' }],
  task_contract: {
    user: '社区居民',
    core_task: '阅读一篇完整访谈',
    object: '口述史文章',
    required: ['可继续阅读'],
    excluded: ['登录'],
  },
  visual_source: 'spec',
  spec_id: '21-editorial-magazine',
  patterns: { selected: ['content-led'], adaptations: ['真实人物照片优先'], rejected: [] },
  acceptance: { pages: ['文章页'], states: ['正常'], viewports: [390, 1280], reopen: '恢复文章入口' },
  selection_profile: {
    task: 'read',
    content_shape: 'long-form',
    content_subject: 'text',
    audience: 'general',
    trust_posture: 'human',
    asset_conditions: 'none-available',
    interaction_intensity: 'low',
    primary_device: 'mobile',
  },
  secret_not_for_packet: 'must not leak through',
};

test('packet contains only the compact handoff and at most three candidate cards', () => {
  const packet = prepareDesign(input, Array.from({ length: 6 }, (_, index) => style(index)));
  assert.equal(packet.project.name, '社区口述史');
  assert.equal(packet.project.ignored, undefined);
  assert.equal(packet.secret_not_for_packet, undefined);
  assert.equal(packet.selection.candidates.length, 3);
  assert.ok(Buffer.byteLength(JSON.stringify(packet)) <= DESIGN_PACKET_MAX_BYTES);
});

test('legacy visual_source is readable without preserving the mixed abstraction', () => {
  const packet = prepareDesign(input, [style(1)]);
  assert.equal(packet.legacy_visual_source, 'spec');
  assert.equal(packet.direction.source, 'project-derived');
  assert.equal(packet.grammar.source, 'packaged-spec');
  assert.equal(packet.grammar.spec_id, '21-editorial-magazine');
  assert.ok(packet.gaps.includes('direction.evidence'));
});

test('oversized packets fail instead of silently dropping evidence', () => {
  const tooLarge = {
    ...input,
    facts: Array.from({ length: 30 }, (_, index) => ({
      source: `source-${index}`,
      value: 'x'.repeat(500),
      evidence: 'measured',
    })),
  };
  assert.throws(() => prepareDesign(tooLarge, [style(1)]), /exceeds/);
});

test('prepare-design CLI emits a usable packet from the packaged catalogs', () => {
  const folder = mkdtempSync(join(tmpdir(), 'design-packet-'));
  const profile = join(folder, 'profile.json');
  writeFileSync(profile, JSON.stringify({
    ...input,
    direction: {
      source: 'project-derived',
      evidence: ['真实访谈文本和手机阅读场景'],
      motif: '逐段展开的口述记录',
      composition: '正文为主轴，人物注释退居侧线',
      project_signature: '每段保留说话者与采集日期',
    },
    grammar: { source: 'packaged-spec', spec_id: '21-editorial-magazine', deviations: [] },
  }));
  const tools = join(dirname(fileURLToPath(import.meta.url)), '..');
  const result = spawnSync(process.execPath, [
    join(tools, 'prepare-design.mjs'), '--profile', profile, '--kind', 'style',
  ], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.schema_version, 1);
  assert.equal(output.selection.status, 'matched');
  assert.equal(output.gaps.length, 0);
});

test('prepare-design CLI writes output atomically and preserves it on an incomplete run', () => {
  const folder = mkdtempSync(join(tmpdir(), 'design-packet-output-'));
  const profile = join(folder, 'profile.json');
  const incompleteProfile = join(folder, 'incomplete.json');
  const outputPath = join(folder, 'nested', 'packet.json');
  writeFileSync(profile, JSON.stringify({
    ...input,
    direction: {
      source: 'project-derived',
      evidence: ['真实访谈文本和手机阅读场景'],
      motif: '逐段展开的口述记录',
      composition: '正文为主轴，人物注释退居侧线',
      project_signature: '每段保留说话者与采集日期',
    },
    grammar: { source: 'packaged-spec', spec_id: '21-editorial-magazine', deviations: [] },
  }));
  writeFileSync(incompleteProfile, JSON.stringify({ industry: '医疗' }));
  const tools = join(dirname(fileURLToPath(import.meta.url)), '..');

  const written = spawnSync(process.execPath, [
    join(tools, 'prepare-design.mjs'), '--profile', profile, '--kind', 'style', '--output', outputPath,
  ], { encoding: 'utf8' });
  assert.equal(written.status, 0, written.stderr);
  assert.equal(JSON.parse(readFileSync(outputPath, 'utf8')).selection.status, 'matched');

  const original = readFileSync(outputPath, 'utf8');
  const incomplete = spawnSync(process.execPath, [
    join(tools, 'prepare-design.mjs'), '--profile', incompleteProfile, '--kind', 'style', '--output', outputPath,
  ], { encoding: 'utf8' });
  assert.equal(incomplete.status, 2);
  assert.equal(readFileSync(outputPath, 'utf8'), original);

  const absentPath = join(folder, 'absent.json');
  const absent = spawnSync(process.execPath, [
    join(tools, 'prepare-design.mjs'), '--profile', incompleteProfile, '--kind', 'style', '--output', absentPath,
  ], { encoding: 'utf8' });
  assert.equal(absent.status, 2);
  assert.equal(existsSync(absentPath), false);
});
