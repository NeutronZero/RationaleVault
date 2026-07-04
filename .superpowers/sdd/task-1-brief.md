# Task 1: Docs Naming Normalization

**Files:**
- Rename: `docs/AGENT_COMPILERS.md` → `docs/agent_compilers.md`
- Rename: `docs/ARCHITECTURE.md` → `docs/architecture.md`
- Rename: `docs/COGNITIVE_HEAD.md` → `docs/cognitive_head.md`
- Rename: `docs/CONTEXT_PLANNER.md` → `docs/context_planner.md`
- Rename: `docs/EVENT_LEDGER.md` → `docs/event_ledger.md`
- Rename: `docs/FREEZE_LEVELS.md` → `docs/freeze_levels.md`
- Rename: `docs/KNOWLEDGE_COMPILER.md` → `docs/knowledge_compiler.md`
- Rename: `docs/evaluation-gates.md` → `docs/evaluation_gates.md`
- Rename: `docs/release-checklist.md` → `docs/release_checklist.md`
- Delete: `docs/event-ledger.md` (duplicate)

## Steps

1. Rename UPPERCASE_SNAKE_CASE docs to lowercase_snake_case using `git mv`
2. Rename kebab-case docs to snake_case using `git mv`
3. Delete duplicate event-ledger.md using `git rm`
4. Grep entire repo for old filename references (including `.relay/` directory)
5. Audit pyproject.toml for doc references
6. Audit CI workflows for doc references
7. Run tests: `pytest -o addopts="" -x -q` — expected: 2022+ passed, 25 skipped
8. Commit with message: "docs: normalize naming to lowercase_snake_case"
