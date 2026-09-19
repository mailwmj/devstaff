# Maintainer guide

Read release/AGENTS.md for the runtime protocol. Do not duplicate control rules here.

The bundle has four skills. Shared code is packaged under site-builder/scripts/site_runtime and imported by sibling check/design scripts. Bundle version, state schema, contract schema and upstream intelligence snapshot are separate identifiers.

Develop changes with regression tests. Preserve explicit legacy tests (schema revision 2) and add schema-3 behavior tests. Never delete tests to manufacture green status. A changed product policy requires a documented changed assertion; incompatible old behavior is not silently revived.

Run tools/verify_all.py and inspect each saved exit code. Optional browser tests exercise supported starters with synthetic records, not production data. The public source tree is not modified by checker. Reports and checks are identity-bound but not a malicious-process security boundary.

Use local/feature/scope revisions appropriately. Review source manifest exclusions. Keep user decisions distinct from test execution and public-operation authorization. Real production release adapters must implement deploy, smoke and rollback and obtain scope/version-specific authorization.

Do not merge or publish automatically. Use reviewable branches and pull requests; attach actual evidence and disclose unrun external/human/host checks.
