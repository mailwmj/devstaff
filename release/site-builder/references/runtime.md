# Runtime, previews and maintenance

## Commands

All paths below are relative to site-builder. Installed skills are siblings; do not copy an individual script without its runtime.

```text
python3 scripts/doctor.py PROJECT
python3 scripts/state.py init PROJECT
python3 scripts/state.py preflight PROJECT
python3 scripts/state.py discover PROJECT --structure single --reason "one clear task" 
python3 scripts/state.py decide PROJECT --task TASK --direction DIRECTION --quote USER_WORDS
python3 ../site-design/scripts/design.py check-contract --root PROJECT --phase prebuild --out REPORT
python3 scripts/state.py start PROJECT --contract-report REPORT
python3 scripts/state.py begin-check PROJECT
python3 ../site-check/scripts/check.py plan PROJECT --compact
python3 ../site-check/scripts/run.py PROJECT --output PROJECT/.site/check/current
python3 scripts/state.py verify PROJECT --report PROJECT/.site/check/current/report.json
python3 scripts/state.py revise PROJECT --change-kind local --reason "specific local correction"
```

The run.py example executes only the supported stdlib starter, not arbitrary projects. Browser output is limited until visual review. Reports refer to the current round ID, mode and fingerprints. Legacy projects use explicit state.py migrate; legacy contracts have an explicit backed-up project.py migrate-contract.

## Preview access

`project.py preview PROJECT RELATIVE_ARTIFACT --kind file|embedded|url|screenshot` creates a versioned record. An optional URL must not carry credentials; public audience needs --public-quote. User access stays unknown until actual user/host evidence is available; local access alone never upgrades it. Generic-local is the tested adapter; other host-specific embedding is not claimed.

## Tested starting points

`scaffold.py NEW_DIRECTORY --profile content|personal|shared --title TITLE` refuses an existing target. All three use Python >=3.10 stdlib plus browser HTML/CSS/JS. No framework download is necessary. Start `server.py`; run `manage.py check`, `manage.py test`, `manage.py build`. Edit content through public/content.json and design tokens through public/styles.css. Existing apps retain their stack instead of migrating to this starter.

Personal/shared state is SQLite on the server computer, not browser localStorage. Reload/closing the browser preserves it; another device does not magically gain access. Shared profile has prompted account setup and per-owner authorization at every data operation; it does not implement organization-wide roles or password reset. Confirm any real team-sharing requirements before extending it.

CSV/JSON import previews every row and commits once. Invalid rows write nothing. Duplicate policy is skip/replace/reject. Monetary values use integer minor units. Export schema 1 is re-importable. Backup uses SQLite's backup API; stop services before a manual restore and retain the old file/WAL state for recovery.

## Release boundaries

The development server is loopback-only and must not be exposed to the Internet. Static content can be built for a reviewed hosting provider. Data profiles require a production server/TLS/provider adapter and separate security checks. No cloud account, credentials, public endpoint or paid resource is created by the package.

release.py plan ARTIFACT DESTINATION --scope preview --owner OWNER --cost DISCLOSURE --out PLAN creates a digest-bound plan. authorize requires its exact SHA and explicit quote. execute uses a tested local-directory provider: copy, smoke, rollback. The provider refuses public scope and never calls local files a public website. Implement real providers through deploy/smoke/rollback and obtain new authorization; command success without entry success is not delivery.

## Installation and recovery

Use install.py as a complete bundle. Shared instructions remain in site-builder/references/AGENTS.md after the source download is removed. Host instructions are never overwritten. Stop using an installation before --replace. Recoverable errors roll back; an interrupted process can leave the documented lock and recovery.json. Inspect retained backups before clearing a lock. Four directory moves are not claimed as one filesystem transaction.

## Evidence boundaries

Checks detect accidental/cooperative-agent errors. Files writable by the same OS user are not a security boundary against a malicious process. Source hashing does not prove correctness or authenticate the user. Browser traces contain only fixture data in the supplied runner; treat external traces as potentially sensitive.
