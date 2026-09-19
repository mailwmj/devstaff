# Final integration notes

The implementation branch contains the complete repository, not a patch-only delivery. Preserve `release/` as the standalone distribution root.

Observed integration failures were corrected rather than hidden:

- Unknown-schema tests now exclude supported schema 3 and still reject unsupported revisions and wrong types.
- A malformed non-object state produces an invalid report instead of raising an uncaught AttributeError.
- Legacy discovering states without a decision normalize to an explicitly unconfirmed empty decision; no approval is manufactured. New states and invalid decision types remain strict.
- Install-source deletion fixtures include the actual shipped runtime dependency. The full clean-release deletion test remains in `verify_all.py`.
- Two distinct confirmations can contain the same words; the CLI regression now asserts the correct preserved decisions rather than requiring different strings.
- Design staged-loading tables and measured sizes were restored, retaining the existing link/size/progressive-loading tests.
- Browser login tests wait for the actual login response and record bounded, synthetic-only diagnostics on failure.
- Reviewed 320px screenshots exposed a clipped native date field and wrapped short logout label. Narrow layout now stacks date/amount fields and preserves action labels.

Routine CI has read-only repository permissions. Temporary source integration workflows and transport files are removed from the final tree. No merge, force push, public deployment or real-data operation was performed.

For exact final success/failure use the CI run bound to the reviewed commit, not earlier runs. The `browser-evidence` artifact includes `summary.json`, every command log, screenshots/traces, `skill.zip` and `devstaff-project.zip`. Visual axes intentionally remain limited in automated product reports until a reviewer checks the specific project's design.
