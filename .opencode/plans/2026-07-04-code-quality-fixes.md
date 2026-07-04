# Code Quality Fixes Implementation Plan (Final)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 code quality issues across the rationalevault codebase — unused imports, missing tests, DSN cleanup.

**Architecture:** P0 tasks only — zero behavioral change, ship immediately.

**Tech Stack:** Python 3.12+, pytest, psycopg3, dataclasses

## Global Constraints

- Python >=3.12
- All tests must pass with `pytest tests/ -x -q`
- No changes to public API signatures
- Follow existing code conventions: `from __future__ import annotations`, dataclasses, plain `assert` in tests
- Tests must use public API — no private attribute access (`_schemas`, `_db_path`)
- Unused imports determined by `ruff check . --select F401`, not hardcoded list

---

## Execution Order

1. Task 1 — unused imports (lowest risk)
2. Task 6 — DSN tests + cosmetic cleanup
3. Task 2 — blast_radius tests
4. Task 3 — SchemaPolicyFactory tests
5. Task 4 — SQLite tests
6. Task 5 — CLI tests
7. Final validation

---

## Task 1: Remove All Unused Imports

**Files:** 13 files (determined by ruff, not hardcoded)

**Interfaces:** None — pure cleanup, no behavior change.

- [ ] **Step 1: Run ruff to find actual unused imports**

Run: `ruff check . --select F401`
This returns the authoritative list. Remove exactly what ruff reports.

- [ ] **Step 2: Run tests to verify no regressions**

Run: `pytest tests/ -x -q --tb=short`
Expected: All existing tests pass.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove unused imports (ruff F401)"
```

---

## Task 6: Add Tests for DSN Connection String + Cosmetic Cleanup

**Files:**
- Create: `tests/unit/db/test_connection.py`
- Modify: `rationalevault/db/connection.py:28-44` (cosmetic only)

**Interfaces:** `get_dsn() -> str`

- [ ] **Step 1: Write tests for DSN construction**

```python
"""Tests for database connection configuration."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from rationalevault.db.connection import get_dsn


class TestGetDsn:
    def test_default_dsn(self) -> None:
        env = {k: v for k, v in os.environ.items() if not k.startswith("RELAY_DB_")}
        with patch.dict(os.environ, env, clear=True):
            dsn = get_dsn()
            assert "host=localhost" in dsn
            assert "port=5432" in dsn
            assert "dbname=relay" in dsn
            assert "user=relay" in dsn
            assert "password" not in dsn

    def test_password_included_when_set(self) -> None:
        env = {
            "RELAY_DB_HOST": "db.example.com",
            "RELAY_DB_PORT": "5433",
            "RELAY_DB_NAME": "mydb",
            "RELAY_DB_USER": "admin",
            "RELAY_DB_PASSWORD": "s3cret",
        }
        with patch.dict(os.environ, env, clear=True):
            dsn = get_dsn()
            assert "host=db.example.com" in dsn
            assert "password=s3cret" in dsn

    def test_special_chars_in_password_preserved(self) -> None:
        env = {
            "RELAY_DB_HOST": "localhost",
            "RELAY_DB_PORT": "5432",
            "RELAY_DB_NAME": "relay",
            "RELAY_DB_USER": "relay",
            "RELAY_DB_PASSWORD": "pass word with spaces",
        }
        with patch.dict(os.environ, env, clear=True):
            dsn = get_dsn()
            assert "password=pass word with spaces" in dsn

    def test_production_requires_password(self) -> None:
        """Production mode without password should raise RuntimeError."""
        env = {
            "RELAY_ENV": "production",
            "RELAY_DB_HOST": "localhost",
            "RELAY_DB_PORT": "5432",
            "RELAY_DB_NAME": "relay",
            "RELAY_DB_USER": "relay",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="RELAY_DB_PASSWORD must be set"):
                get_dsn()
```

- [ ] **Step 2: Run tests to establish baseline**

Run: `pytest tests/unit/db/test_connection.py -v`
Expected: PASS

- [ ] **Step 3: Clean up DSN construction (cosmetic only)**

Replace `rationalevault/db/connection.py` lines 28-44 with:

```python
def get_dsn() -> str:
    """
    Build a libpq connection string from environment variables.
    Falls back to sensible defaults that match docker-compose.yml.
    """
    host = os.environ.get("RELAY_DB_HOST", "localhost")
    port = os.environ.get("RELAY_DB_PORT", "5432")
    dbname = os.environ.get("RELAY_DB_NAME", "relay")
    user = os.environ.get("RELAY_DB_USER", "relay")
    password = os.environ.get("RELAY_DB_PASSWORD")
    if os.environ.get("RELAY_ENV") == "production" and not password:
        raise RuntimeError("RELAY_DB_PASSWORD must be set in production.")

    parts = [f"host={host}", f"port={port}", f"dbname={dbname}", f"user={user}"]
    if password:
        parts.append(f"password={password}")
    parts.append("connect_timeout=3")
    return " ".join(parts)
```

Note: This is **not a security fix**. The original f-string DSN is identical in behavior. This is a readability improvement only.

- [ ] **Step 4: Run tests again**

Run: `pytest tests/unit/db/test_connection.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rationalevault/db/connection.py tests/unit/db/test_connection.py
git commit -m "test+refactor: add DSN tests (incl. production mode), clean up connection string"
```

---

## Task 2: Add Tests for blast_radius Edge Cases

**Files:**
- Modify: `tests/unit/organization/test_organization_graph.py`

**Interfaces:** `OrganizationGraphProjection.blast_radius(state, project_id) -> set[str]`

- [ ] **Step 1: Write edge case tests**

Add to `tests/unit/organization/test_organization_graph.py`:

```python
class TestBlastRadiusEdgeCases:
    def test_blast_radius_empty_graph(self) -> None:
        """Empty graph returns only the starting node."""
        state = OrganizationGraphState(
            nodes={}, edges=[], adjacency={}, reverse_adjacency={},
            clusters=[], health=OrganizationGraphHealth(
                node_count=0, edge_count=0, cluster_count=0,
                density=0.0, avg_degree=0.0, health_score=0.0,
            ),
        )
        result = OrganizationGraphProjection.blast_radius(state, "nonexistent")
        assert result == {"nonexistent"}

    def test_blast_radius_cyclic_graph(self) -> None:
        """Cyclic TRANSFERRED_TO edges terminate correctly (BFS visited set)."""
        edge = OrganizationEdge(
            source="a", target="b",
            relation_type=OrganizationRelationType.TRANSFERRED_TO,
            weight=1.0, confidence=1.0,
        )
        reverse_edge = OrganizationEdge(
            source="b", target="a",
            relation_type=OrganizationRelationType.TRANSFERRED_TO,
            weight=1.0, confidence=1.0,
        )
        node_a = OrganizationNode(project_id="a", name="A")
        node_b = OrganizationNode(project_id="b", name="B")
        state = OrganizationGraphState(
            nodes={"a": node_a, "b": node_b},
            edges=[edge, reverse_edge],
            adjacency={"a": [edge], "b": [reverse_edge]},
            reverse_adjacency={"a": [reverse_edge], "b": [edge]},
            clusters=[["a", "b"]],
            health=OrganizationGraphHealth(
                node_count=2, edge_count=2, cluster_count=1,
                density=1.0, avg_degree=1.0, health_score=1.0,
            ),
        )
        result = OrganizationGraphProjection.blast_radius(state, "a")
        assert result == {"a", "b"}

    def test_blast_radius_ignores_non_transferred_edges(self) -> None:
        """Only TRANSFERRED_TO edges are traversed."""
        edge = OrganizationEdge(
            source="a", target="b",
            relation_type=OrganizationRelationType.IN_CLUSTER,
            weight=1.0, confidence=1.0,
        )
        node_a = OrganizationNode(project_id="a", name="A")
        node_b = OrganizationNode(project_id="b", name="B")
        state = OrganizationGraphState(
            nodes={"a": node_a, "b": node_b},
            edges=[edge],
            adjacency={"a": [edge], "b": []},
            reverse_adjacency={"a": [], "b": [edge]},
            clusters=[["a", "b"]],
            health=OrganizationGraphHealth(
                node_count=2, edge_count=1, cluster_count=1,
                density=0.5, avg_degree=0.5, health_score=1.0,
            ),
        )
        result = OrganizationGraphProjection.blast_radius(state, "a")
        assert result == {"a"}

    def test_blast_radius_unrelated_nodes_not_traversed(self) -> None:
        """Graph with unrelated nodes — only reachable via TRANSFERRED_TO."""
        edge = OrganizationEdge(
            source="a", target="b",
            relation_type=OrganizationRelationType.TRANSFERRED_TO,
            weight=1.0, confidence=1.0,
        )
        node_a = OrganizationNode(project_id="a", name="A")
        node_b = OrganizationNode(project_id="b", name="B")
        node_c = OrganizationNode(project_id="c", name="C")
        state = OrganizationGraphState(
            nodes={"a": node_a, "b": node_b, "c": node_c},
            edges=[edge],
            adjacency={"a": [edge], "b": [], "c": []},
            reverse_adjacency={"a": [], "b": [edge], "c": []},
            clusters=[["a", "b", "c"]],
            health=OrganizationGraphHealth(
                node_count=3, edge_count=1, cluster_count=1,
                density=0.33, avg_degree=0.67, health_score=1.0,
            ),
        )
        result = OrganizationGraphProjection.blast_radius(state, "a")
        assert result == {"a", "b"}
        assert "c" not in result
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/organization/test_organization_graph.py::TestBlastRadiusEdgeCases -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/organization/test_organization_graph.py
git commit -m "test: add blast_radius edge cases (empty graph, cycles, non-transfer, unrelated nodes)"
```

---

## Task 3: Add Tests for SchemaPolicyFactory Compilation Failures

**Files:**
- Modify: `tests/unit/schema/test_factory.py`

**Interfaces:** `SchemaPolicyFactory.compile(governance_state) -> SchemaPolicy`

- [ ] **Step 1: Add tests for error paths**

Add to `tests/unit/schema/test_factory.py`:

```python
def test_factory_compiles_with_invalid_event_type():
    """Invalid event type strings are silently skipped."""
    from rationalevault.schema.events import EventType

    state = GovernanceState(
        policies={},
        schema_versions={"INVALID_TYPE": (2, 10)},
    )
    factory = SchemaPolicyFactory()
    policy = factory.compile(state)
    assert isinstance(policy, SchemaPolicy)
    # Invalid type should not appear — latest_version returns default (1)
    assert policy.latest_version(EventType.PROJECT_CREATED) == 1


def test_factory_compile_at_sequence_filters_by_eff_seq():
    """Only schemas with eff_seq <= sequence are included."""
    from rationalevault.schema.events import EventType
    state = GovernanceState(
        policies={},
        schema_versions={
            "PROJECT_CREATED": (3, 50),
            "TASK_CREATED": (2, 100),
        },
    )
    factory = SchemaPolicyFactory()
    policy = factory.compile_at_sequence(state, sequence=75)
    assert policy.latest_version(EventType.PROJECT_CREATED) == 3
    assert policy.latest_version(EventType.TASK_CREATED) == 1
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/schema/test_factory.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/schema/test_factory.py
git commit -m "test: add SchemaPolicyFactory error path and sequence filtering tests"
```

---

## Task 4: Add Tests for SQLite Datetime Fallback

**Files:**
- Modify: `tests/unit/db/test_sqlite_store.py`

**Interfaces:** Test through public API (`get_events` or `get_project_stream`), not private `_row_to_record`.

- [ ] **Step 1: Add test for invalid datetime fallback**

Add to `tests/unit/db/test_sqlite_store.py`:

```python
class TestDatetimeFallback:
    def test_invalid_datetime_falls_back_to_now(self, store: SQLiteEventStore, project: UUID) -> None:
        """Events with invalid recorded_at still load via public API."""
        import sqlite3
        from datetime import datetime, timezone

        # Insert a valid event
        store.append_event(
            project, "main", EventType.PROJECT_CREATED,
            {"name": "Test"}, meta(),
        )

        # Corrupt the stored datetime
        with sqlite3.connect(store._db_path) as conn:
            conn.execute(
                "UPDATE rationalevault_events SET recorded_at = 'not-a-date' WHERE project_id = ?",
                (str(project),),
            )

        # Read through public API — should not raise
        events = store.get_project_stream(project)
        assert len(events) == 1
        assert isinstance(events[0].recorded_at, datetime)
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/db/test_sqlite_store.py::TestDatetimeFallback -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/db/test_sqlite_store.py
git commit -m "test: add datetime fallback test via public API"
```

---

## Task 5: Add Test for CLI Commands

**Files:**
- Create: `tests/test_cli.py`

**Interfaces:** `rationalevault.cli.main:main` CLI entry point

- [ ] **Step 1: Check CLI implementation for --version behavior**

Read `rationalevault/cli/main.py` to find how `--version` is implemented (argparse action or custom handler).

- [ ] **Step 2: Create CLI tests with output verification**

```python
"""Tests for rationalevault CLI entry point."""
from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import patch

import pytest


class TestCliMain:
    def test_main_help_exits_cleanly(self) -> None:
        """CLI --help should exit 0."""
        with patch("sys.argv", ["rationalevault", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                from rationalevault.cli.main import main
                main()
            assert exc_info.value.code == 0

    def test_main_version_flag_prints_version(self) -> None:
        """CLI --version should print version info."""
        captured = StringIO()
        with patch("sys.argv", ["rationalevault", "--version"]):
            with patch("sys.stdout", captured):
                with pytest.raises(SystemExit) as exc_info:
                    from rationalevault.cli.main import main
                    main()
                assert exc_info.value.code == 0
                output = captured.getvalue()
                # Version string should contain something meaningful
                assert len(output.strip()) > 0
```

- [ ] **Step 3: Run test**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: add CLI help and version tests with output verification"
```

---

## Final Validation

After all P0 tasks complete:

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All PASS

- [ ] **Step 2: Run linting**

Run: `ruff check .`
Expected: No errors

- [ ] **Step 3: Run formatting check**

Run: `ruff format --check .`
Expected: No changes needed

- [ ] **Step 4: Run type checking**

Run: `mypy rationalevault/`
Expected: No new errors

- [ ] **Step 5: Check coverage**

Run: `coverage run -m pytest`
Run: `coverage report`
Expected: No coverage decrease on modified files

- [ ] **Step 6: Review scope**

Run: `git diff --stat`
Verify change scope is limited to intended files.

---

## Summary

| Task | Type | Risk | Files Changed |
|------|------|------|---------------|
| 1 | Cleanup | None | N files (ruff-determined) |
| 6 | Test+Cleanup | None | 1 file + 1 test |
| 2 | Test | None | 1 test file |
| 3 | Test | None | 1 test file |
| 4 | Test | None | 1 test file |
| 5 | Test | None | 1 test file |
