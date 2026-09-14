#!/usr/bin/env node
import { mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';

import { prepareDesign } from './lib/design-packet.mjs';
import { loadCandidates } from './select.mjs';

function parseArgs(argv) {
  const args = { kind: 'all', limit: 3 };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--profile') args.profile = argv[++index];
    else if (token === '--state') args.state = argv[++index];
    else if (token === '--output') args.output = argv[++index];
    else if (token === '--kind') args.kind = argv[++index];
    else if (token === '--limit') args.limit = Number(argv[++index]);
    else throw new Error(`Unknown argument: ${token}`);
  }
  if (!args.profile) throw new Error('Usage: node tools/prepare-design.mjs --profile profile.json [--state state.json] [--kind style|template|all] [--output packet.json]');
  if (!['style', 'template', 'all'].includes(args.kind)) throw new Error('--kind must be style, template, or all');
  if (!Number.isInteger(args.limit) || args.limit < 1) throw new Error('--limit must be a positive integer');
  return args;
}

function writeJsonAtomic(path, value) {
  const destination = resolve(path);
  const folder = dirname(destination);
  mkdirSync(folder, { recursive: true });
  const temporary = `${destination}.${randomUUID()}.tmp`;
  try {
    writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
    renameSync(temporary, destination);
  } finally {
    rmSync(temporary, { force: true });
  }
  return destination;
}

try {
  const args = parseArgs(process.argv.slice(2));
  const input = JSON.parse(readFileSync(resolve(args.profile), 'utf8'));
  const state = args.state ? JSON.parse(readFileSync(resolve(args.state), 'utf8')) : undefined;
  const packet = prepareDesign(input, loadCandidates(args.kind), {
    kind: args.kind,
    limit: args.limit,
    state,
  });
  const complete = packet.gaps.length === 0 && packet.selection.status === 'matched';
  if (args.output && complete) {
    const output = writeJsonAtomic(args.output, packet);
    console.log(JSON.stringify({ status: 'written', output, bytes: Buffer.byteLength(JSON.stringify(packet)) }));
  } else {
    const stream = args.output ? process.stderr : process.stdout;
    stream.write(`${JSON.stringify(packet, null, 2)}\n`);
  }
  if (!complete) process.exitCode = 2;
} catch (error) {
  console.error(JSON.stringify({ error: error.message }));
  process.exitCode = 2;
}
