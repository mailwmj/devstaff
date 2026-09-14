import test from 'node:test';
import assert from 'node:assert/strict';

import { selectDesign } from '../lib/selector.mjs';

const candidates = [
  {
    id: 'quiet-editorial',
    kind: 'style',
    name: 'Quiet editorial',
    file: 'quiet.md',
    semantic: {
      tasks: ['read'],
      content_shapes: ['long-form'],
      content_subjects: ['text'],
      audiences: ['general'],
      trust_postures: ['authoritative'],
      asset_conditions: ['none-available'],
      interaction_intensities: ['low'],
      primary_devices: ['mobile', 'desktop'],
    },
    constraints: {
      color_schemes: ['light'],
      requires_images: false,
      visual_risk: 'low',
      motion_dependency: 'none',
    },
    strengths: ['long reading'],
    tradeoffs: ['low promotional energy'],
    reject_conditions: ['dense continuous operations'],
  },
  {
    id: 'image-premium',
    kind: 'style',
    name: 'Image premium',
    file: 'image.md',
    semantic: {
      tasks: ['persuade'],
      content_shapes: ['image-gallery'],
      content_subjects: ['physical-product'],
      audiences: ['consumer'],
      trust_postures: ['aspirational'],
      asset_conditions: ['image-required'],
      interaction_intensities: ['low'],
      primary_devices: ['mobile', 'desktop'],
    },
    constraints: {
      color_schemes: ['dark'],
      requires_images: true,
      visual_risk: 'medium',
      motion_dependency: 'optional',
    },
    strengths: ['strong product imagery'],
    tradeoffs: ['depends on photography'],
    reject_conditions: ['no usable imagery'],
  },
  {
    id: 'design-method',
    kind: 'method',
    name: 'A design method',
    file: 'method.md',
    semantic: {},
    constraints: {},
    strengths: [],
    tradeoffs: [],
    reject_conditions: [],
  },
];

test('industry-only input cannot select a style', () => {
  const result = selectDesign({ industry: 'publishing' }, candidates);
  assert.equal(result.status, 'needs_profile');
  assert.deepEqual(result.candidates, []);
  assert.ok(result.missing.includes('task'));
  assert.ok(result.missing.includes('content_shape'));
});

test('semantic evidence ranks candidates and explains the match', () => {
  const result = selectDesign({
    task: 'read',
    content_shape: 'long-form',
    content_subject: 'text',
    audience: 'general',
    trust_posture: 'authoritative',
    asset_conditions: 'none-available',
    interaction_intensity: 'low',
    primary_device: 'mobile',
  }, candidates, { kind: 'style', limit: 3 });

  assert.equal(result.status, 'matched');
  assert.equal(result.candidates[0].id, 'quiet-editorial');
  assert.ok(result.candidates[0].reasons.some(reason => reason.field === 'task'));
  assert.equal(result.candidates.some(candidate => candidate.id === 'design-method'), false);
});

test('hard constraints reject before semantic ranking', () => {
  const result = selectDesign({
    task: 'persuade',
    content_shape: 'image-gallery',
    audience: 'consumer',
    constraints: {
      color_scheme: 'light',
      images_available: false,
      max_visual_risk: 'low',
    },
  }, candidates, { kind: 'style' });

  assert.equal(result.status, 'no_match');
  const rejected = result.rejected.find(candidate => candidate.id === 'image-premium');
  assert.ok(rejected);
  assert.deepEqual(
    rejected.reasons.sort(),
    ['color-scheme:dark', 'images-required', 'visual-risk:medium'].sort(),
  );
});

test('selection limit is capped at three', () => {
  const repeated = Array.from({ length: 6 }, (_, index) => ({
    ...candidates[0],
    id: `candidate-${index}`,
  }));
  const result = selectDesign({
    task: 'read',
    content_shape: 'long-form',
    audience: 'general',
  }, repeated, { limit: 99 });
  assert.equal(result.candidates.length, 3);
});
