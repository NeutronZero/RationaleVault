# Task 2: Example Consolidation

**Files:**
- Delete: `examples/basic_memory/` (dir)
- Delete: `examples/knowledge_synthesis/` (dir)
- Delete: `examples/multi_agent_handoff/` (dir)
- Delete: `examples/todo_api/` (dir)
- Create: `rationalevault/examples/todo_api.py` (from `examples/todo_api/main.py`)
- Move: `examples/first_experiment.md` → `docs/first_experiment.md`
- Delete: `examples/` (empty after above)

## Steps

1. Read `examples/todo_api/main.py` and create `rationalevault/examples/todo_api.py` as a single-file module
2. Move `examples/first_experiment.md` → `docs/first_experiment.md` via `git mv`
3. Delete top-level example directories via `git rm -r`
4. Remove empty `examples/` directory
5. Grep for references to old example paths and update any found
6. Run tests: `pytest -o addopts="" -x -q` — expected: 2022+ passed, 25 skipped
7. Commit with message: "docs: consolidate examples into rationalevault/examples"
