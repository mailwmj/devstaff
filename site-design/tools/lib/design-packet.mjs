import { selectDesign } from './selector.mjs';

export const DESIGN_PACKET_MAX_BYTES = 12_000;

function pick(source, keys) {
  const output = {};
  for (const key of keys) {
    if (source && source[key] !== undefined) output[key] = source[key];
  }
  return output;
}

function legacyLayers(input) {
  const legacy = input.visual_source;
  const directionSource = legacy === 'existing'
    ? 'existing'
    : legacy === 'reference'
      ? 'reference'
      : 'project-derived';
  const grammarSource = legacy === 'existing'
    ? 'existing-system'
    : legacy === 'spec'
      ? 'packaged-spec'
      : 'project-tokens';
  return {
    direction: {
      source: directionSource,
      evidence: [],
      motif: '',
      composition: '',
      project_signature: '',
    },
    grammar: {
      source: grammarSource,
      ...(input.spec_id ? { spec_id: input.spec_id } : {}),
      deviations: input.deviations || [],
    },
  };
}

function normalizeLayers(input) {
  const legacy = input.visual_source ? legacyLayers(input) : {};
  return {
    direction: pick(input.direction || legacy.direction || {}, [
      'source', 'evidence', 'motif', 'composition', 'project_signature',
    ]),
    grammar: pick(input.grammar || legacy.grammar || {}, [
      'source', 'spec_id', 'deviations',
    ]),
    patterns: pick(input.patterns || {}, ['selected', 'adaptations', 'rejected']),
  };
}

function gapsFor(layers) {
  const gaps = [];
  if (!Array.isArray(layers.direction.evidence) || layers.direction.evidence.length === 0) {
    gaps.push('direction.evidence');
  }
  for (const field of ['motif', 'composition', 'project_signature']) {
    if (!layers.direction[field]) gaps.push(`direction.${field}`);
  }
  if (!layers.grammar.source) gaps.push('grammar.source');
  return gaps;
}

/** Build the only handoff the builder and checker need for one design run. */
export function prepareDesign(input, candidates, options = {}) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('Design input must be a JSON object');
  }
  const profile = input.selection_profile || input.profile || input;
  const layers = normalizeLayers(input);
  const packet = {
    schema_version: 1,
    project: pick(input.project || {}, ['name', 'root', 'work_type', 'language']),
    facts: Array.isArray(input.facts)
      ? input.facts.map(fact => pick(fact, ['source', 'value', 'evidence']))
      : [],
    task_contract: pick(input.task_contract || {}, [
      'user', 'scenario', 'core_task', 'object', 'content_shape', 'required',
      'recommended', 'confirm', 'excluded', 'flows', 'localization',
    ]),
    ...layers,
    acceptance: pick(input.acceptance || {}, [
      'pages', 'states', 'viewports', 'core_task', 'failure_recovery', 'reopen',
    ]),
    selection: selectDesign(profile, candidates, {
      kind: options.kind || 'all',
      limit: options.limit || 3,
    }),
    gaps: gapsFor(layers),
  };
  if (input.visual_source) packet.legacy_visual_source = input.visual_source;
  if (options.state) {
    packet.state = pick(options.state, [
      'stage', 'concept_confirmed', 'structure_confirmed', 'visual_confirmed',
      'development_authorized',
    ]);
  }
  const bytes = Buffer.byteLength(JSON.stringify(packet));
  if (bytes > DESIGN_PACKET_MAX_BYTES) {
    throw new Error(`DesignPacket exceeds ${DESIGN_PACKET_MAX_BYTES} bytes (${bytes}); reduce facts or acceptance detail`);
  }
  return packet;
}
