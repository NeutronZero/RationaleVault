# Structural Cleanup Design

**Date:** 2026-06-30
**Status:** Approved
**Scope:** Repository-wide structural normalization across 5 anomaly areas

## Context

Repository structural audit identified 5 anomalies: docs naming collisions, example duplication, missing `__init__.py` markers, flat test layout, and singular/plural naming mismatches. This cleanup normalizes all 5 in 5 independent commits.

## Approach

**One commit per anomaly area** (5 commits total). Each is self-contained and reviewable.

---

## Commit 1: Docs Naming Normalization

**Standard:** `lowercase_snake_case.md` for all docs files.

### Renames

| Current | New |
|---|---|
| `AGENT_COMPILERS.md` | `agent_compilers.md` |
| `ARCHITECTURE.md` | `architecture.md` |
| `COGNITIVE_HEAD.md` | `cognitive_head.md` |
| `CONTEXT_PLANNER.md` | `context_planner.md` |
| `EVENT_LEDGER.md` | `event_ledger.md` |
| `FREEZE_LEVELS.md` | `freeze_levels.md` |
| `KNOWLEDGE_COMPILER.md` | `knowledge_compiler.md` |
| `evaluation-gates.md` | `evaluation_gates.md` |
| `release-checklist.md` | `release_checklist.md` |
| `event-ledger.md` | *delete (duplicate of EVENT_LEDGER.md)* |

### Files Already Correct (no change)

`compilers.md`, `concepts.md`, `context.md`, `evaluation.md`, `graph.md`, `knowledge.md`, `memory.md`, `philosophy.md`, `roadmap.md`, `quickstart.md`, `plugin_sdk.md`, `skill_runtime_architecture.md`, all `v*.md` freeze docs.

### Post-Rename Reference Updates

1. Grep entire repo for old filenames in: README.md, CONTRIBUTING.md, other docs, CI workflows
2. Audit `pyproject.toml` — currently only `readme = "README.md"` (no doc renames needed there)
3. Audit `.github/workflows/*` for any doc path references

---

## Commit 2: Example Consolidation

Consolidate to `rationalevault/examples/` (internal package). Delete top-level `examples/` directory entirely.

| Example | Action |
|---|---|
| `basic_memory` | Delete `examples/basic_memory/`, keep `rationalevault/examples/basic_memory.py` |
| `knowledge_synthesis` | Delete `examples/knowledge_synthesis/`, keep `rationalevault/examples/knowledge_synthesis.py` |
| `multi_agent_handoff` | Delete `examples/multi_agent_handoff/`, keep `rationalevault/examples/multi_agent_handoff.py` |
| `todo_api` | Create `rationalevault/examples/todo_api.py` from `examples/todo_api/main.py`, delete `examples/todo_api/` |
| `first_experiment.md` | Move to `docs/first_experiment.md` |
| `examples/` dir | Remove entirely after all contents relocated |

---

## Commit 3: Add Missing `__init__.py` Files

Add empty `__init__.py` to 5 directories (all verified to contain `.py` files but lack package markers):

| Directory | Files inside |
|---|---|
| `rationalevault/cli/` | `main.py` |
| `rationalevault/diagnostics/` | `doctor.py` |
| `rationalevault/extraction/` | `extractor.py`, `prompt.py`, `models.py`, `suggestor.py`, `validator.py` |
| `rationalevault/memory/` | 27 `.py` files |
| `rationalevault/schema/` | `events.py`, `factory.py`, `identifier_registry.py`, `policy.py`, `resolver.py`, `upcaster.py` |

All files are empty `__init__.py` — no logic, just package markers.

---

## Commit 4: Test Suite Layout Normalization

Create subdirectories matching source modules. Move test files from flat `tests/unit/` into organized subdirs.

### Moves

| Source module | Test subdirectory | Files moved |
|---|---|---|
| `cognitive_head/` | `tests/unit/cognitive_head/` | `test_cognitive_head.py`, `test_cognitive_reducer.py`, `test_e2e_cognitive_loop.py` |
| `compilers/` | `tests/unit/compilers/` | `test_claude_compiler.py`, `test_context_compilers.py`, `test_g3_context_compiler.py`, `test_recommendation_compiler.py` |
| `db/` | `tests/unit/db/` | `test_event_store.py`, `test_sqlite_store.py`, `test_event_store_contract.py` |
| `evaluation/` | `tests/unit/evaluation/` | 11 files (`test_evaluation.py`, `test_context_evaluation.py`, `test_knowledge_evaluation.py`, etc.) |
| `mcp/` | `tests/unit/mcp/` | 8 files (`test_mcp_server.py`, `test_h3_mcp_server_v2.py`, etc.) |
| `memory/` | `tests/unit/memory/` | 5 files (`test_memory_foundation.py`, `test_memory_intelligence.py`, etc.) |
| `recommendations/` | `tests/unit/recommendations/` | 5 files (`test_recommendation_*.py`) |
| `retrieval/` | `tests/unit/retrieval/` | 7 files (`test_context_retrieval.py`, `test_retrieval_*.py`) |
| `organization/` | `tests/unit/organization/` *(exists)* | 12 flat files moved in (total 14 with existing 2) |

Cross-cutting tests (architecture guards, stress, benchmarks, migration, governance, skill platform, etc.) remain flat in `tests/unit/`.

### Path Issues Requiring Fixup

3 files have path-sensitive code that breaks when moved deeper:

**`test_evaluation.py` (line 77):**
```python
# CURRENT (assumes tests/unit/ depth):
project_root = Path(__file__).resolve().parent.parent.parent
# FIX FOR tests/unit/evaluation/ depth:
project_root = Path(__file__).resolve().parent.parent.parent.parent
```

**`test_event_store.py` (line 66) and `test_sqlite_store.py` (line 54):**
```python
# Both import from test_event_store_contract via relative import:
from .test_event_store_contract import EventStoreContract
# FIX: Move test_event_store_contract.py to tests/unit/db/ alongside both files
```

### Post-Move Verification

- Each new subdirectory gets an `__init__.py`
- Run `pytest` full suite to confirm no breakage
- Grep for stale path references

---

## Commit 5: Singular/Plural Naming Normalization

Rename test files in `tests/unit/recommendations/` to match the plural source module name:

| Current | New |
|---|---|
| `test_recommendation_engine.py` | `test_recommendations_engine.py` |
| `test_recommendation_evaluator.py` | `test_recommendations_evaluator.py` |
| `test_recommendation_models.py` | `test_recommendations_models.py` |
| `test_recommendation_compiler.py` | `test_recommendations_compiler.py` |
| `test_recommendation_cli_mcp.py` | `test_recommendations_cli_mcp.py` |

---

## Verification (All Commits)

After all 5 commits:
1. `pytest` — full suite passes (2022+ tests, 25 skipped)
2. `python -c "import rationalevault"` — package imports cleanly
3. `git diff --stat` — only renames/adds, no content changes (except path fixes in Commit 4)
4. Grep for any remaining references to old filenames
