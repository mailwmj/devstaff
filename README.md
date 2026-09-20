# Devstaff: progressive website skills 1.2

Four cooperating skills help nontechnical people turn a concrete task into a usable, maintainable website. site-builder owns orchestration; site-brief clarifies scope; site-design owns visible design; site-check provides evidence. User conversation stays in the user's language.

## Install and start

Only release/ is distributed. It includes scripts, design knowledge, tests and a shared runtime. Existing projects retain their stack. New projects can use tested content/personal/shared Web starter profiles.

```text
python3 release/install.py /path/to/skills
python3 /path/to/skills/site-builder/scripts/doctor.py /path/to/project
python3 /path/to/skills/site-builder/scripts/state.py init /path/to/project
```

The installer returns a persistent instruction_file under site-builder/references/AGENTS.md. Integrate that reference with the host without overwriting existing instructions. --replace requires stopping use of the old installation; ordinary failures roll back. Interrupted-process recovery is documented in the runtime reference.

## What changed

New state schema 3 supports brief-gated decisions, two information-architecture candidates before any visual work (a single-structure assessment is refused and a direction confirmation stays blocked until a candidate is selected), reference-first visual choices, automatic isolated verification, revision-scoped confirmation, local/feature/scope changes, stable action/error payloads and explicit legacy migration. The main states remain compatible. Reports bind round, project mode, source and contract; they are read once. Core-not-run cannot become usable delivery. Changing risks cannot quietly weaken a report.

The brief is a gate, not a note. A new website starts with its question round: schema revision 3 records the answers and explicit assumptions in `.site/brief.md` and refuses a direction confirmation without that record, and preflight exposes the stop as `user_gate: brief_questions`. Legacy revision 2 projects keep their old gate until `state.py migrate`, which seeds a marked brief.

Contract schema 2 keeps acceptance targets in one structured block, with Markdown for explanation. Existing contracts remain readable. Source hashing prunes dependencies and supports a fingerprinted include/exclude policy for readonly product data.

Visual alternatives follow the reference question. A new surface compares two structure skeletons first; after the user picks one, a supplied reference yields a single aligned version and no reference yields two style candidates. Shared DOM is legal for style comparisons; arbitrary dark-mode, reskin wording, star character and aesthetic recipe gates are removed. The existing rich design knowledge and upstream data snapshot remain packaged.

The starter foundation includes real SQLite persistence, validated money/date values, transactional import preview, reversible export, request idempotency and per-owner shared-backend authorization. It binds loopback, not public Internet. Cloud/production adapters and real external operations require separate configuration, authorization and verification.

## Verification

```text
python3 tools/verify_all.py
python3 tools/verify_all.py --browser
```

Every suite saves its command, exit code and logs. Browser mode requires optional pinned Playwright and a browser. It uses isolated synthetic data and saves screenshots/trace. Visual approval and independent checking are not fabricated. Release validation archives the actual commit, installs it into a new location, removes the install source and runs shipped checks/doctor/starter tests. dist/skill.zip is the complete release bundle; dist/devstaff-project.zip is the complete source snapshot.

See docs/implementation-progress.md for exact implementation status and limits. evals/cases.json and evals/README.md distinguish real agent records, scripted fixtures and human review. Do not interpret scripted smoke tests as a user study or an arbitrary-stack guarantee.

## Compatibility and safety

Python >=3.10, standard library for runtime/starters. Browser testing is optional. CI covers Python 3.10/3.12 on Linux; unsupported host/OS capabilities stay unavailable/unknown. All four skills are installed as siblings. No public deployment, cloud account or paid resource is created automatically.
