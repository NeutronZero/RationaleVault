# Task 4: Test Suite Layout Normalization

**Files:**
- Create 8 new test subdirectories with `__init__.py`
- Move 51+ test files from flat `tests/unit/` into subdirectories
- Fix path references in 1 file (`test_evaluation.py`)

## Directories to Create

```
tests/unit/cognitive_head/__init__.py
tests/unit/compilers/__init__.py
tests/unit/db/__init__.py
tests/unit/evaluation/__init__.py
tests/unit/mcp/__init__.py
tests/unit/memory/__init__.py
tests/unit/recommendations/__init__.py
tests/unit/retrieval/__init__.py
```

## File Moves

### cognitive_head/ (3 files)
- `test_cognitive_head.py`
- `test_cognitive_reducer.py`
- `test_e2e_cognitive_loop.py`

### compilers/ (4 files)
- `test_claude_compiler.py`
- `test_context_compilers.py`
- `test_g3_context_compiler.py`
- `test_recommendation_compiler.py`

### db/ (3 files)
- `test_event_store.py`
- `test_event_store_contract.py`
- `test_sqlite_store.py`

### evaluation/ (8 files)
- `test_context_evaluation.py`
- `test_evaluation.py`
- `test_knowledge_evaluation.py`
- `test_retrieval_evaluation.py`
- `test_cross_project_evaluator.py`
- `test_graph_projection_evaluator.py`
- `test_recommendation_evaluator.py`
- `test_retrieval_evaluator.py`

### mcp/ (8 files)
- `test_cross_project_cli_mcp.py`
- `test_h3_mcp_server_v2.py`
- `test_mcp_server.py`
- `test_organization_cli_mcp.py`
- `test_organization_continuation_cli_mcp.py`
- `test_organization_graph_cli_mcp.py`
- `test_recommendation_cli_mcp.py`
- `test_retrieval_cli_mcp.py`

### memory/ (5 files)
- `test_h4_memory_integration.py`
- `test_h5_memory_policy.py`
- `test_memory_foundation.py`
- `test_memory_intelligence.py`
- `test_phase6_memory_lifecycle.py`

### recommendations/ (2 files)
- `test_recommendation_engine.py`
- `test_recommendation_models.py`

### retrieval/ (4 files)
- `test_context_retrieval.py`
- `test_retrieval_context.py`
- `test_retrieval_intelligence.py`
- `test_retrieval_orchestrator.py`

### organization/ (12 files, moving into existing dir)
- `test_organization_benchmark.py`
- `test_organization_cli_mcp.py`
- `test_organization_continuation.py`
- `test_organization_continuation_cli_mcp.py`
- `test_organization_continuation_evaluator.py`
- `test_organization_evaluator.py`
- `test_organization_graph.py`
- `test_organization_graph_benchmark.py`
- `test_organization_graph_cli_mcp.py`
- `test_organization_graph_evaluator.py`
- `test_organization_models.py`
- `test_organization_projection.py`

## Path Fixup Required

In `tests/unit/evaluation/test_evaluation.py`, find:
```python
project_root = Path(__file__).resolve().parent.parent.parent
```
Change to:
```python
project_root = Path(__file__).resolve().parent.parent.parent.parent
```

## Steps

1. Create 8 new subdirectories with `__init__.py`
2. Move all files using `git mv` (one category at a time)
3. Fix `test_evaluation.py` path reference
4. Run tests: `pytest -o addopts="" -x -q`
5. Commit with message: "test: reorganize unit tests into subdirectories"

## Important
- Only move files listed above. Do NOT move any other files.
- Only modify `test_evaluation.py` for the path fixup. No other content changes.
- Cross-cutting tests (architecture guards, stress, benchmarks, etc.) remain flat.
