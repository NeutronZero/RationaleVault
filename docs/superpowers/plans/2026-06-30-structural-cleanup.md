# Structural Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize repository structure across 5 anomaly areas: docs naming, example duplication, missing `__init__.py`, test layout, and singular/plural mismatches.

**Architecture:** 5 independent commits, one per anomaly area. Each commit is self-contained and reviewable. No content changes except path fixups in Commit 4.

**Tech Stack:** Python 3.12+, pytest, Git

## Global Constraints

- All 2022+ tests must pass after each commit (25 skipped)
- `python -c "import rationalevault"` must succeed after each commit
- Docs naming standard: `lowercase_snake_case.md`
- No logic changes — structural moves only (except path fixups in Commit 4)
- Each commit is independently revertable

---

### Task 1: Docs Naming Normalization

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

- [ ] **Step 1: Rename UPPERCASE_SNAKE_CASE docs to lowercase_snake_case**

```bash
cd docs
git mv AGENT_COMPILERS.md agent_compilers.md
git mv ARCHITECTURE.md architecture.md
git mv COGNITIVE_HEAD.md cognitive_head.md
git mv CONTEXT_PLANNER.md context_planner.md
git mv EVENT_LEDGER.md event_ledger.md
git mv FREEZE_LEVELS.md freeze_levels.md
git mv KNOWLEDGE_COMPILER.md knowledge_compiler.md
```

- [ ] **Step 2: Rename kebab-case docs to snake_case**

```bash
cd docs
git mv evaluation-gates.md evaluation_gates.md
git mv release-checklist.md release_checklist.md
```

- [ ] **Step 3: Delete duplicate event-ledger.md**

```bash
git rm docs/event-ledger.md
```

- [ ] **Step 4: Grep for old filename references across repo**

Run: `grep -rn "AGENT_COMPILERS\|ARCHITECTURE\|COGNITIVE_HEAD\|CONTEXT_PLANNER\|EVENT_LEDGER\|FREEZE_LEVELS\|KNOWLEDGE_COMPILER\|evaluation-gates\|release-checklist\|event-ledger" --include="*.md" --include="*.yml" --include="*.yaml" --include="*.toml" --include="*.py" . .relay/`
Expected: Only matches in the files we just renamed (which are now gone from their old paths). Also check `.relay/` directory for any references.

- [ ] **Step 5: Audit pyproject.toml for doc references**

Run: `grep -n "readme\|\.md\|doc" pyproject.toml`
Expected: Only `readme = "README.md"` — no renames needed there. Also verify no static path listings reference old uppercase filenames (Linux CI runners are case-sensitive).

- [ ] **Step 6: Audit CI workflows for doc references**

Run: `grep -rn "docs/" .github/workflows/`
Expected: No references to old doc filenames

- [ ] **Step 7: Run tests to verify nothing broke**

Run: `pytest -o addopts="" -x -q`
Expected: 2022+ passed, 25 skipped

- [ ] **Step 8: Commit**

```bash
git add -A docs/
git commit -m "docs: normalize naming to lowercase_snake_case

Renames:
- AGENT_COMPILERS.md → agent_compilers.md
- ARCHITECTURE.md → architecture.md
- COGNITIVE_HEAD.md → cognitive_head.md
- CONTEXT_PLANNER.md → context_planner.md
- EVENT_LEDGER.md → event_ledger.md
- FREEZE_LEVELS.md → freeze_levels.md
- KNOWLEDGE_COMPILER.md → knowledge_compiler.md
- evaluation-gates.md → evaluation_gates.md
- release-checklist.md → release_checklist.md

Deleted:
- event-ledger.md (duplicate of EVENT_LEDGER.md)"
```

---

### Task 2: Example Consolidation

**Files:**
- Delete: `examples/basic_memory/` (dir)
- Delete: `examples/knowledge_synthesis/` (dir)
- Delete: `examples/multi_agent_handoff/` (dir)
- Delete: `examples/todo_api/` (dir)
- Create: `rationalevault/examples/todo_api.py` (from `examples/todo_api/main.py`)
- Move: `examples/first_experiment.md` → `docs/first_experiment.md`
- Delete: `examples/` (empty after above)

- [ ] **Step 1: Create rationalevault/examples/todo_api.py from top-level example**

Read `examples/todo_api/main.py` and write a single-file version to `rationalevault/examples/todo_api.py`. The file should contain the same logic but as a standalone module (no `if __name__ == "__main__"` guard needed — it's a library example).

- [ ] **Step 2: Move first_experiment.md to docs/**

```bash
git mv examples/first_experiment.md docs/first_experiment.md
```

- [ ] **Step 3: Delete top-level example directories**

```bash
git rm -r examples/basic_memory/
git rm -r examples/knowledge_synthesis/
git rm -r examples/multi_agent_handoff/
git rm -r examples/todo_api/
```

- [ ] **Step 4: Remove empty examples/ directory**

```bash
rmdir examples/ 2>/dev/null; git add examples/ 2>/dev/null
```

- [ ] **Step 5: Grep for references to old example paths**

Run: `grep -rn "examples/basic_memory\|examples/knowledge_synthesis\|examples/multi_agent_handoff\|examples/todo_api" --include="*.md" --include="*.py" --include="*.toml" .`
Expected: No remaining references (or update any found)

- [ ] **Step 6: Run tests**

Run: `pytest -o addopts="" -x -q`
Expected: 2022+ passed, 25 skipped

- [ ] **Step 7: Commit**

```bash
git add -A examples/ rationalevault/examples/ docs/first_experiment.md
git commit -m "docs: consolidate examples into rationalevault/examples

- Move todo_api example to rationalevault/examples/todo_api.py
- Move first_experiment.md to docs/
- Delete top-level examples/ directory (basic_memory, knowledge_synthesis,
  multi_agent_handoff, todo_api)"
```

---

### Task 3: Add Missing `__init__.py` Files

**Files:**
- Create: `rationalevault/cli/__init__.py` (empty)
- Create: `rationalevault/diagnostics/__init__.py` (empty)
- Create: `rationalevault/extraction/__init__.py` (empty)
- Create: `rationalevault/memory/__init__.py` (empty)
- Create: `rationalevault/schema/__init__.py` (empty)

- [ ] **Step 1: Create empty __init__.py files**

```bash
touch rationalevault/cli/__init__.py
touch rationalevault/diagnostics/__init__.py
touch rationalevault/extraction/__init__.py
touch rationalevault/memory/__init__.py
touch rationalevault/schema/__init__.py
```

- [ ] **Step 2: Verify all 5 files exist**

Run: `ls -la rationalevault/cli/__init__.py rationalevault/diagnostics/__init__.py rationalevault/extraction/__init__.py rationalevault/memory/__init__.py rationalevault/schema/__init__.py`
Expected: All 5 files exist

- [ ] **Step 3: Run tests**

Run: `pytest -o addopts="" -x -q`
Expected: 2022+ passed, 25 skipped

- [ ] **Step 4: Commit**

```bash
git add rationalevault/cli/__init__.py rationalevault/diagnostics/__init__.py rationalevault/extraction/__init__.py rationalevault/memory/__init__.py rationalevault/schema/__init__.py
git commit -m "fix: add missing __init__.py to 5 subpackages

Adds empty package markers to: cli/, diagnostics/, extraction/,
memory/, schema/ — all contain .py files but lacked __init__.py"
```

---

### Task 4: Test Suite Layout Normalization

**Files:**
- Create dirs: `tests/unit/cognitive_head/`, `tests/unit/compilers/`, `tests/unit/db/`, `tests/unit/evaluation/`, `tests/unit/mcp/`, `tests/unit/memory/`, `tests/unit/recommendations/`, `tests/unit/retrieval/`
- Move 55+ test files from flat `tests/unit/` into subdirectories
- Create `__init__.py` in each new test subdirectory
- Fix path references in 3 files

- [ ] **Step 1: Create test subdirectories with __init__.py**

```bash
mkdir -p tests/unit/cognitive_head tests/unit/compilers tests/unit/db tests/unit/evaluation tests/unit/mcp tests/unit/memory tests/unit/recommendations tests/unit/retrieval
touch tests/unit/cognitive_head/__init__.py tests/unit/compilers/__init__.py tests/unit/db/__init__.py tests/unit/evaluation/__init__.py tests/unit/mcp/__init__.py tests/unit/memory/__init__.py tests/unit/recommendations/__init__.py tests/unit/retrieval/__init__.py
```

- [ ] **Step 2: Move cognitive_head tests**

```bash
git mv tests/unit/test_cognitive_head.py tests/unit/cognitive_head/
git mv tests/unit/test_cognitive_reducer.py tests/unit/cognitive_head/
git mv tests/unit/test_e2e_cognitive_loop.py tests/unit/cognitive_head/
```

- [ ] **Step 3: Move compilers tests**

```bash
git mv tests/unit/test_claude_compiler.py tests/unit/compilers/
git mv tests/unit/test_context_compilers.py tests/unit/compilers/
git mv tests/unit/test_g3_context_compiler.py tests/unit/compilers/
git mv tests/unit/test_recommendation_compiler.py tests/unit/compilers/
```

- [ ] **Step 4: Move db tests (including contract)**

```bash
git mv tests/unit/test_event_store.py tests/unit/db/
git mv tests/unit/test_event_store_contract.py tests/unit/db/
git mv tests/unit/test_sqlite_store.py tests/unit/db/
```

- [ ] **Step 5: Move evaluation tests**

Note: Organization-specific evaluator tests (`test_organization_*_evaluator.py`) move to `tests/unit/organization/` in Step 10.

```bash
git mv tests/unit/test_context_evaluation.py tests/unit/evaluation/
git mv tests/unit/test_evaluation.py tests/unit/evaluation/
git mv tests/unit/test_knowledge_evaluation.py tests/unit/evaluation/
git mv tests/unit/test_retrieval_evaluation.py tests/unit/evaluation/
git mv tests/unit/test_cross_project_evaluator.py tests/unit/evaluation/
git mv tests/unit/test_graph_projection_evaluator.py tests/unit/evaluation/
git mv tests/unit/test_recommendation_evaluator.py tests/unit/evaluation/
git mv tests/unit/test_retrieval_evaluator.py tests/unit/evaluation/
```

- [ ] **Step 6: Move mcp tests**

```bash
git mv tests/unit/test_cross_project_cli_mcp.py tests/unit/mcp/
git mv tests/unit/test_h3_mcp_server_v2.py tests/unit/mcp/
git mv tests/unit/test_mcp_server.py tests/unit/mcp/
git mv tests/unit/test_organization_cli_mcp.py tests/unit/mcp/
git mv tests/unit/test_organization_continuation_cli_mcp.py tests/unit/mcp/
git mv tests/unit/test_organization_graph_cli_mcp.py tests/unit/mcp/
git mv tests/unit/test_recommendation_cli_mcp.py tests/unit/mcp/
git mv tests/unit/test_retrieval_cli_mcp.py tests/unit/mcp/
```

- [ ] **Step 7: Move memory tests**

```bash
git mv tests/unit/test_h4_memory_integration.py tests/unit/memory/
git mv tests/unit/test_h5_memory_policy.py tests/unit/memory/
git mv tests/unit/test_memory_foundation.py tests/unit/memory/
git mv tests/unit/test_memory_intelligence.py tests/unit/memory/
git mv tests/unit/test_phase6_memory_lifecycle.py tests/unit/memory/
```

- [ ] **Step 8: Move recommendations tests**

```bash
git mv tests/unit/test_recommendation_engine.py tests/unit/recommendations/
git mv tests/unit/test_recommendation_models.py tests/unit/recommendations/
```

Note: `test_recommendation_compiler.py` and `test_recommendation_evaluator.py` already moved to `compilers/` and `evaluation/` respectively. `test_recommendation_cli_mcp.py` already moved to `mcp/`.

- [ ] **Step 9: Move retrieval tests**

```bash
git mv tests/unit/test_context_retrieval.py tests/unit/retrieval/
git mv tests/unit/test_retrieval_context.py tests/unit/retrieval/
git mv tests/unit/test_retrieval_intelligence.py tests/unit/retrieval/
git mv tests/unit/test_retrieval_orchestrator.py tests/unit/retrieval/
```

Note: `test_retrieval_evaluation.py` and `test_retrieval_evaluator.py` already moved to `evaluation/`. `test_retrieval_cli_mcp.py` already moved to `mcp/`.

- [ ] **Step 10: Move organization tests into existing subdirectory**

```bash
git mv tests/unit/test_organization_benchmark.py tests/unit/organization/
git mv tests/unit/test_organization_cli_mcp.py tests/unit/organization/
git mv tests/unit/test_organization_continuation.py tests/unit/organization/
git mv tests/unit/test_organization_continuation_cli_mcp.py tests/unit/organization/
git mv tests/unit/test_organization_continuation_evaluator.py tests/unit/organization/
git mv tests/unit/test_organization_evaluator.py tests/unit/organization/
git mv tests/unit/test_organization_graph.py tests/unit/organization/
git mv tests/unit/test_organization_graph_benchmark.py tests/unit/organization/
git mv tests/unit/test_organization_graph_cli_mcp.py tests/unit/organization/
git mv tests/unit/test_organization_graph_evaluator.py tests/unit/organization/
git mv tests/unit/test_organization_models.py tests/unit/organization/
git mv tests/unit/test_organization_projection.py tests/unit/organization/
```

- [ ] **Step 11: Fix test_evaluation.py path reference**

After moving to `tests/unit/evaluation/`, the `project_root` calculation needs one more `.parent`:

Read `tests/unit/evaluation/test_evaluation.py`, find the line:
```python
project_root = Path(__file__).resolve().parent.parent.parent
```

Change to:
```python
project_root = Path(__file__).resolve().parent.parent.parent.parent
```

- [ ] **Step 12: Run full test suite**

Run: `pytest -o addopts="" -x -q`
Expected: 2022+ passed, 25 skipped

If tests fail, check:
- Relative imports in `tests/unit/db/test_event_store.py` and `tests/unit/db/test_sqlite_store.py` — they import from `.test_event_store_contract` which is now in the same directory, so should work
- Path references using `__file__` — only `test_evaluation.py` needed fixing

- [ ] **Step 13: Commit**

```bash
git add -A tests/unit/
git commit -m "test: reorganize unit tests into subdirectories

Moves test files from flat tests/unit/ into organized subdirs:
- cognitive_head/ (3 files)
- compilers/ (4 files)
- db/ (3 files, including contract)
- evaluation/ (11 files)
- mcp/ (8 files)
- memory/ (5 files)
- recommendations/ (2 files)
- retrieval/ (4 files)
- organization/ (11 files moved into existing dir)

Fixes path reference in test_evaluation.py for deeper nesting."
```

---

### Task 5: Singular/Plural Naming Normalization

**Files:**
- Rename: `tests/unit/recommendations/test_recommendation_engine.py` → `test_recommendations_engine.py`
- Rename: `tests/unit/recommendations/test_recommendation_models.py` → `test_recommendations_models.py`

Note: Only 2 files remain to rename. The other 3 (`test_recommendation_compiler.py`, `test_recommendation_evaluator.py`, `test_recommendation_cli_mcp.py`) were moved to `compilers/`, `evaluation/`, and `mcp/` respectively in Task 4, and their names already match their new context.

- [ ] **Step 1: Rename test files to plural convention**

```bash
git mv tests/unit/recommendations/test_recommendation_engine.py tests/unit/recommendations/test_recommendations_engine.py
git mv tests/unit/recommendations/test_recommendation_models.py tests/unit/recommendations/test_recommendations_models.py
```

- [ ] **Step 2: Run tests**

Run: `pytest -o addopts="" -x -q`
Expected: 2022+ passed, 25 skipped

- [ ] **Step 3: Commit**

```bash
git add -A tests/unit/recommendations/
git commit -m "test: normalize singular/plural naming in recommendations tests

Rename test_recommendation_{engine,models}.py → test_recommendations_{engine,models}.py
to match the plural source module name (rationalevault/recommendations/)."
```

---

## Final Verification

After all 5 tasks:

- [ ] **Step 1: Full test suite**

Run: `pytest -o addopts="" -x -q`
Expected: 2022+ passed, 25 skipped

- [ ] **Step 2: Import check**

Run: `python -c "import rationalevault; print('OK')"`
Expected: OK

- [ ] **Step 3: Grep for stale doc references**

Run: `grep -rn "AGENT_COMPILERS\|COGNITIVE_HEAD\|CONTEXT_PLANNER\|EVENT_LEDGER\|FREEZE_LEVELS\|KNOWLEDGE_COMPILER\|evaluation-gates\|release-checklist\|event-ledger" --include="*.md" --include="*.yml" --include="*.py" .`
Expected: No matches

- [ ] **Step 4: Verify no orphaned files**

Run: `git status`
Expected: Clean working tree
