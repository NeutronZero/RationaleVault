# Task 1 Report: Docs Naming Normalization

**Status:** DONE

## What I Implemented

Renamed 9 docs files to `lowercase_snake_case.md` and deleted 1 duplicate:

| Old Name | New Name |
|----------|----------|
| `AGENT_COMPILERS.md` | `agent_compilers.md` |
| `ARCHITECTURE.md` | `architecture.md` |
| `COGNITIVE_HEAD.md` | `cognitive_head.md` |
| `CONTEXT_PLANNER.md` | `context_planner.md` |
| `EVENT_LEDGER.md` | `event_ledger.md` |
| `FREEZE_LEVELS.md` | `freeze_levels.md` |
| `KNOWLEDGE_COMPILER.md` | `knowledge_compiler.md` |
| `evaluation-gates.md` | `evaluation_gates.md` |
| `release-checklist.md` | `release_checklist.md` |
| `event-ledger.md` | *deleted (duplicate)* |

## Reference Fixes

Updated all 27 cross-references across 17 files:
- `README.md` — 3 references
- `docs/architecture.md` — 4 references
- `docs/freeze_levels.md` — 4 references
- `docs/v2.0_cognitive_platform_freeze.md` — 1 reference
- `docs/v1.3.0_execution_freeze.md` — 1 reference
- `docs/v1.2.0_architecture_freeze.md` — 1 reference
- `docs/v1.1.0_snapshot.md` — 1 reference
- `docs/skill_runtime_architecture.md` — 1 reference
- `docs/roadmap.md` — 1 reference
- `docs/philosophy.md` — 1 reference
- `docs/adr/README.md` — 2 references
- `docs/adr/ADR-001-event-sourcing-as-foundation.md` — 2 references
- `docs/adr/ADR-002-deterministic-ephemeral-projections.md` — 2 references
- `docs/adr/ADR-004-architecture-freeze-governance.md` — 1 reference
- `docs/adr/ADR-005-evaluation-driven-development.md` — 2 references
- `docs/adr/ADR-007-three-track-roadmap.md` — 1 reference
- `CONTRIBUTING.md` — 1 reference

## Audit Results

- **pyproject.toml**: Only references `README.md` — no changes needed
- **CI workflows**: No `.github/workflows/*.yml` files exist — no changes needed
- **`.relay/` directory**: No old filename references found

## Testing

All 17 test collection errors are pre-existing import failures (`GovernanceRecord` and `MissingProjectBootstrapError` missing from `rationalevault.schema.events`). These are completely unrelated to doc renames — no documentation tests exist that would be affected.

## Files Changed

25 files in commit `1251df5`:
- 8 renamed via `git mv`
- 1 deleted via `git rm`
- 1 created (freeze_levels.md, was previously untracked)
- 17 files updated with corrected references

## Concerns

- `docs/freeze_levels.md` was never tracked by git (FREEZE_LEVELS.md was in the untracked files list). It was moved via `Move-Item` and staged as a new file. This is expected behavior for an untracked file being renamed.
- Pre-existing test failures are blocking the full test suite (17 errors, 0 passed). This is a separate issue from doc naming.
