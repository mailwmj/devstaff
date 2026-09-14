#!/usr/bin/env node
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { selectDesign } from './lib/selector.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const STYLE_CATALOG = join(HERE, '..', 'assets', 'spec', 'catalog.json');
const TEMPLATE_CATALOG = join(HERE, '..', '..', 'site-builder', 'assets', 'templates', 'catalog.json');

export function loadCandidates(kind = 'style') {
  const candidates = [];
  if (kind === 'style' || kind === 'all') {
    const catalog = JSON.parse(readFileSync(STYLE_CATALOG, 'utf8'));
    candidates.push(...catalog.specs.filter(spec => spec.kind === 'style'));
  }
  if (kind === 'template' || kind === 'all') {
    if (!existsSync(TEMPLATE_CATALOG)) {
      throw new Error('Template catalog is missing; install the complete site Skill suite');
    }
    const catalog = JSON.parse(readFileSync(TEMPLATE_CATALOG, 'utf8'));
    candidates.push(...catalog.templates.map(template => ({ ...template, kind: 'template' })));
  }
  return candidates;
}

function parseArgs(argv) {
  const args = { kind: 'style', limit: 3 };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--profile') args.profile = argv[++index];
    else if (token === '--kind') args.kind = argv[++index];
    else if (token === '--limit') args.limit = Number(argv[++index]);
    else throw new Error(`Unknown argument: ${token}`);
  }
  if (!args.profile) throw new Error('Usage: node tools/select.mjs --profile profile.json [--limit 3] [--kind style|template|all]');
  if (!['style', 'template', 'all'].includes(args.kind)) throw new Error('--kind must be style, template, or all');
  if (!Number.isInteger(args.limit) || args.limit < 1) throw new Error('--limit must be a positive integer');
  return args;
}

export function run(argv) {
  const args = parseArgs(argv);
  const profile = JSON.parse(readFileSync(resolve(args.profile), 'utf8'));
  return selectDesign(profile, loadCandidates(args.kind), { kind: args.kind, limit: args.limit });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    const result = run(process.argv.slice(2));
    console.log(JSON.stringify(result, null, 2));
    if (result.status !== 'matched') process.exitCode = 2;
  } catch (error) {
    console.error(JSON.stringify({ error: error.message }));
    process.exitCode = 2;
  }
}
