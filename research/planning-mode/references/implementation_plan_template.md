# Implementation Plan: [Feature/Bug Name]

[Brief description of what is being implemented or changed, the motivation, and background context.]

## User Review Required

> [!IMPORTANT]
> [Highlight any critical architectural decisions, breaking changes, or trade-offs that the user must be aware of.]

- **Breaking Changes**: [List if any, else "None"]
- **Architecture Decisions**: [List key architectural assumptions]

## Open Questions

> [!NOTE]
> [Questions that need user clarification before or during implementation. If none, specify "None identified".]

- **Q1**: [Description of uncertainty and suggested options]

---

## Proposed Changes

### [Component / Layer Name]

#### [NEW | MODIFY | DELETE] `[relative/path/to/file]`
- **Action**: [New file creation / Existing file modification / Deletion]
- **Key Symbols**: [`functionName`, `ClassName`, `interfaceName`]
- **Description**: [Precise breakdown of changes, logic added/removed, and callers affected]

---

## Verification Plan

### Automated Tests
- [ ] Run test suite: `[e.g. npm test / pytest tests/path / go test ./...]`
- [ ] Linting & Type checking: `[e.g. npm run typecheck / flake8 / tsc --noEmit]`
- [ ] New unit tests to write:
  - `[test_file.py::test_case_name]`: verifies [specific business scenario]

### Manual Verification
- [ ] [Step 1: start server / invoke CLI]
- [ ] [Step 2: trigger behavior and inspect output / UI state]
- [ ] [Step 3: verify edge cases or error handling]
