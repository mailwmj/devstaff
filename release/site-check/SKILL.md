---
name: site-check
description: Generate check plans, execute supported isolated browser probes and validate version-bound evidence. Use for working websites and explicit check-only requests; never mutate product source or self-certify independence.
---
# Evidence-based verification

Read the shared protocol at the sibling site-builder/references/AGENTS.md (installed), or ../AGENTS.md (source bundle). Apply its user-language guidance. 

`check.py plan PROJECT` is authoritative for project mode, target axes, source/contract fingerprints and round_id. Use `--compact` to put the large source manifest in an artifact. Read notable exclusions; product seed databases can be explicitly included in `.site/source-policy.json`. Policy changes invalidate evidence. No file-suffix shortcut proves impact.

`check.py validate-report PROJECT FILE` validates one report. Exit 0 means protocol-valid (overall may still be blocked), 1 invalid report, 2 execution/input error. Builder consumes the exact validated snapshot, not a second file read. Source/contract/mode/round identity must match. Core/static/negative checks are necessary for usable delivery; insufficient visual/device coverage may be limited only with explicit limits. Never reuse a previous report by replacing its hash.

## Execution

For the packaged stdlib Web starter only, `run.py PROJECT --output .site/check/RUN` snapshots recognized product sources, runs their syntax/domain checks, starts a loopback test server with a fresh synthetic database, and runs real browser probes. Install optional pinned requirements-browser.txt only in an approved test environment. `--standalone` is a fixture test and cannot be submitted as product delivery evidence.

Targets bind actual supported probe IDs: starter.core, starter.negative, starter.reopen, starter.desktop, starter.mobile, starter.risk. A bound name must match its axis and observable standard. Unknown application-specific targets are not_run, not assumed covered. Zero matched elements fail at the probe. Missing browser, failed backend or console errors never become a fabricated success.

The runner saves command exit codes, synthetic-environment metadata, screenshots and trace. It leaves visual axes limited until an actual reviewer inspects the relevant renders. It always declares independent:false. Strict needs a genuinely separate checker context; a different skill name is not independence.

For other stacks use the host's supported test/browser adapter and follow the same evidence/side-effect rules. Do not pretend this runner is universal. Source is read-only; fixture data writes are allowed. Real messages, payments and sensitive/production data writes need specific authorization.

Read user-visible promises beyond the contract: README, button text and empty-state copy. Inspect real behavior, including one likely failure and reopening. Return verified/limited/blocked, artifacts, evidence and limitations to builder, never directly declare delivery or fix source.
