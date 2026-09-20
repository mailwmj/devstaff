---
name: site-builder
description: Default website creation, implementation and revision entry. Coordinate brief, design and read-only checks; preserve confirmed decisions for small edits.
---
# Website orchestration

Read the shared protocol at the sibling site-builder/references/AGENTS.md (installed), or ../AGENTS.md (source bundle). Apply its user-language guidance. 

Run scripts relative to this skill directory. Start with `doctor.py PROJECT`, then `state.py preflight PROJECT`. For a new/major project run `state.py init PROJECT`; no `.site` is needed for an unmanaged small edit. Resume by reading state, brief summary, applicable contract targets and unfinished journal entries.

## Decision and build

New website: the next user-visible reply is the brief question round, not a plan. While preflight reports the `brief_questions` gate, do not write an implementation plan, page list, stack, file layout or source; the answers and assumptions go into `.site/brief.md`, and `decide` refuses without a valid block. If the host requires a plan first, its first section is that question round.

Ask site-brief for missing product facts. Ask site-design for the smallest visible experiment that resolves a real decision. Default to one recommendation; register single/choice structure assessment. `select-structure` is needed only for choice. `decide` records the actual user's product decision; don't invent a quote.

Write the contract, run `design.py check-contract --phase prebuild`, and pass its report to `state.py start --contract-report FILE`. Use vertical slices; test each observable result. Keep mutable work progress in the journal, not the frozen contract. Existing code/stack wins; empty projects may use `scaffold.py DEST --profile content|personal|shared --title TITLE`.

## Revision and verification

Managed small edit: `revise --change-kind local --reason ...`. Added feature: feature; changed main task: scope. Preserve unrelated decisions; new risks use `--risk permissions` etc. Never repair a validation problem by reducing risk mode.

After cheap checks, show a registered preview when useful. Schema 3 `begin-check` starts isolated checks without asking permission for ordinary tests. The checker reads product source and may write only disposable fixtures. Close a failed round with cancel-check before changing code, then create a fresh round. `verify --report FILE` is the only transition to usable delivery. Reports include the current round_id returned by plan.

Legacy projects: `state.py migrate PROJECT` makes a backup and enables the new loop. Do not silently change old behavior.

## Operating references

Read [runtime and maintenance](references/runtime.md) for supported commands, storage, release boundaries and local previews. For design standards read only the current site-design branch. For checks use site-check. Return user-facing results, not internal traces.
