const FIELDS = [
  ['task', 'tasks', 5],
  ['content_shape', 'content_shapes', 5],
  ['content_subject', 'content_subjects', 4],
  ['audience', 'audiences', 2],
  ['trust_posture', 'trust_postures', 3],
  ['asset_conditions', 'asset_conditions', 3],
  ['interaction_intensity', 'interaction_intensities', 3],
  ['primary_device', 'primary_devices', 2],
];

const RISK = { low: 0, medium: 1, high: 2 };

function values(value) {
  if (Array.isArray(value)) return value.map(normalize).filter(Boolean);
  const normalized = normalize(value);
  return normalized ? [normalized] : [];
}

function normalize(value) {
  return typeof value === 'string'
    ? value.trim().toLowerCase().replace(/[\s_]+/g, '-')
    : '';
}

function profileGaps(profile) {
  const missing = [];
  if (!values(profile.task).length) missing.push('task');
  if (!values(profile.content_shape).length) missing.push('content_shape');
  const context = [
    'content_subject', 'audience', 'trust_posture', 'asset_conditions',
    'interaction_intensity', 'primary_device',
  ].some(field => values(profile[field]).length);
  if (!context) missing.push('one_context_dimension');
  return missing;
}

function hardRejections(profile, candidate) {
  const constraints = profile.constraints || {};
  const candidateConstraints = candidate.constraints || {};
  const rejected = [];
  const requestedScheme = normalize(constraints.color_scheme);
  const schemes = values(candidateConstraints.color_schemes);
  if (requestedScheme && schemes.length && !schemes.includes(requestedScheme)) {
    rejected.push(`color-scheme:${schemes.join('+')}`);
  }
  if (constraints.images_available === false && candidateConstraints.requires_images === true) {
    rejected.push('images-required');
  }
  const maximumRisk = normalize(constraints.max_visual_risk);
  const candidateRisk = normalize(candidateConstraints.visual_risk);
  if (maximumRisk in RISK && candidateRisk in RISK && RISK[candidateRisk] > RISK[maximumRisk]) {
    rejected.push(`visual-risk:${candidateRisk}`);
  }
  if (constraints.reduced_motion === true && candidateConstraints.motion_dependency === 'essential') {
    rejected.push('motion-essential');
  }
  if (values(constraints.exclude_ids).includes(normalize(candidate.id))) {
    rejected.push('explicitly-excluded');
  }
  return rejected;
}

function semanticScore(profile, candidate) {
  const reasons = [];
  let score = 0;
  for (const [profileField, candidateField, weight] of FIELDS) {
    const wanted = values(profile[profileField]);
    const offered = values(candidate.semantic?.[candidateField]);
    const matches = wanted.filter(value => offered.includes(value));
    if (!matches.length) continue;
    score += weight;
    reasons.push({ field: profileField, matches, weight });
  }
  return { score, reasons };
}

function allowedKind(candidateKind, requestedKind) {
  if (requestedKind === 'all') return candidateKind === 'style' || candidateKind === 'template';
  return candidateKind === requestedKind;
}

function card(candidate, score, reasons) {
  return {
    id: candidate.id,
    kind: candidate.kind,
    name: candidate.name,
    file: candidate.file,
    score,
    reasons,
    strengths: candidate.strengths || [],
    tradeoffs: candidate.tradeoffs || [],
    reject_conditions: candidate.reject_conditions || [],
  };
}

/**
 * Rank design assets through one public seam. Industry labels are deliberately
 * ignored: callers must provide task, content shape and one contextual fact.
 */
export function selectDesign(profile, candidates, options = {}) {
  const kind = options.kind || 'style';
  if (!['style', 'template', 'all'].includes(kind)) {
    throw new Error('kind must be style, template, or all');
  }
  const limit = Math.min(3, Math.max(1, Number(options.limit) || 3));
  const missing = profileGaps(profile || {});
  if (missing.length) {
    return {
      schema_version: 1,
      status: 'needs_profile',
      missing,
      ignored: profile?.industry ? ['industry'] : [],
      candidates: [],
      rejected: [],
    };
  }

  const ranked = [];
  const rejected = [];
  for (const candidate of candidates || []) {
    if (!allowedKind(candidate.kind, kind)) continue;
    const hard = hardRejections(profile, candidate);
    if (hard.length) {
      rejected.push({ id: candidate.id, kind: candidate.kind, reasons: hard });
      continue;
    }
    const { score, reasons } = semanticScore(profile, candidate);
    const hasCoreMatch = reasons.some(reason => reason.field === 'task' || reason.field === 'content_shape');
    if (!hasCoreMatch || score < 7) {
      rejected.push({ id: candidate.id, kind: candidate.kind, reasons: ['weak-semantic-match'] });
      continue;
    }
    ranked.push(card(candidate, score, reasons));
  }
  ranked.sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
  return {
    schema_version: 1,
    status: ranked.length ? 'matched' : 'no_match',
    missing: [],
    ignored: profile?.industry ? ['industry'] : [],
    candidates: ranked.slice(0, limit),
    rejected,
  };
}
