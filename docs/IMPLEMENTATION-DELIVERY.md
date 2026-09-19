# Devstaff 1.2 implementation delivery

Branch: `agent/devstaff-complete-20260919`. Review: PR #2, targeting `dev-up`. No automatic merge or production deployment.

## Implemented surfaces

| Roadmap | Implementation |
|---|---|
| T00 | Full-suite runner, clean release archive, install-source deletion and installed doctor/tests |
| T01-T02 | Schema 3 state transitions, explicit legacy migration, structured actions/errors, bundle doctor and skill metadata |
| T03-T04 | Local/feature/scope revisions; preserve unaffected decisions; recommended direction first; isolated verification without repeated user permission |
| T05-T06 | Preview identity/access/audience records; schema 2 contract targets; shared deterministic parser; explicit migration backup |
| T07 | Single-read report validation; version/round binding; pruned source scan and explicit read-only asset inclusion |
| T08 | Structure/style/interaction comparison separation; shared DOM allowed; subjective style heuristics no longer deterministic blockers; retained design library |
| T09-T11 | One maintained stdlib Web foundation with content/personal/shared profiles, real SQLite data and server-side owner authorization, import/export, idempotency and backups; isolated Playwright execution |
| T12 | Version-specific local release plan/approval/smoke/rollback adapter; external hosting stays an explicit adapter boundary |
| T13 | Scenario definitions, result validation and comparison tooling with explicit scripted/real-agent/human provenance |
| T14 | Python 3.10/3.12 and browser CI; independent release and full-project archives; complete command logs and browser traces |

## Scope limits

Implementation completeness does not mean every external integration has been implemented or tested. The supported reference runtime is Python standard library plus plain HTML/CSS/JS. Existing projects retain their own stack; the bundle does not force migration. The shared profile is an owner-private multi-account backend foundation, not a ready-made organization collaboration product.

No cloud account, domain or paid resource was created. The local development server is loopback-only and is not a production server. Public deployments of data applications require a production adapter, TLS and deployment-specific validation. The included release adapter validates the process locally rather than pretending it deployed to a cloud.

No real customer/student data was used. No real-user study or independent-Agent benchmark results were fabricated. The eval infrastructure is implemented; a measured study requires actual runs. Screenshots and geometry probes are not a substitute for visual review; reports preserve limited/not_run where applicable.

## Verification and artifacts

Run `python3 tools/verify_all.py`; add `--browser` after explicitly installing the pinned optional browser dependencies. The runner writes `.verification/summary.json` plus per-command logs. Every failed check remains a failure; required empty selector measurements fail.

GitHub Actions artifacts contain `skill.zip` (the complete standalone `release/`) and `devstaff-project.zip` (the entire source tree), together with `.verification/`. Compare `summary.json`'s `commit` to the reviewed commit. An archive from a failed run is not an approved release.

PR #2 records the final observed CI result and exact commit. Earlier failed integration runs are retained as history. Temporary transport payloads and the write-enabled source integration workflow have been removed from the final tree; routine verification has read-only repository permissions.
