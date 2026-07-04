# RationaleVault v1.2.0 → v1.2.1 Architectural Review — Update Patch

**Purpose:** Corrections and additions to apply to the v1.2.0 Architectural Review to produce v1.2.1.

**Scope note:** This patch addresses factual corrections only. The architectural thesis, analysis, and conclusions of the v1.2.0 review remain unchanged where factually supported.

---

## A. Scope Declaration (Add to top of review)

Add after the **Method note** paragraph:

> **Review basis:** This review is based on the **published v1.2.0 repository** as tracked by `git ls-files` on `NeutronZero/RationaleVault` (main branch). Local unpublished work-in-progress is intentionally excluded from the review scope. Where local development work is relevant to the roadmap, it is noted as such.

---

## B. Factual Corrections

### B1. Codebase Metrics (Executive Summary)

| Field | v1.2.0 Says | v1.2.1 Corrects To | Evidence |
|-------|-------------|---------------------|----------|
| Source LOC | 24,424 | **38,443** | `(Get-ChildItem rationalevault/ -Recurse -Filter *.py \| Get-Content \| Measure-Object -Line).Lines` |
| Source modules | 16 | **22** | `git ls-files rationalevault/ \| Split-Path -Parent -Unique` (top-level) |
| Test LOC | 18,378 | **27,138** | `(Get-ChildItem tests/ -Recurse -Filter *.py \| Get-Content \| Measure-Object -Line).Lines` |
| Test files | 90 | **134** | `Get-ChildItem tests/ -Recurse -Filter test_*.py \| Measure-Object` |

### B2. MCP Tool Count (§1.2 diagram, §6)

| Field | v1.2.0 Says | v1.2.1 Corrects To | Evidence |
|-------|-------------|---------------------|----------|
| MCP tools | 18 | **17** | `mcp/tools.py`: 15 read + 2 write `@server.tool()` decorators |

Update diagram label: `MCP Server - 17 tools`

### B3. Logging Count (§1.7 Weaknesses)

| Field | v1.2.0 Says | v1.2.1 Corrects To | Evidence |
|-------|-------------|---------------------|----------|
| Files importing `logging` | 1 | **2** | `projections/governance.py:3`, `projections/alias.py:2` |

Update wording: "Two source files reference `logging`"

### B4. Silent Exception Count (§1.7 Weaknesses)

| Field | v1.2.0 Says | v1.2.1 Corrects To | Evidence |
|-------|-------------|---------------------|----------|
| `except Exception:` occurrences | not quantified | **66 across 31 files** | `grep -r "except Exception:" rationalevault/ --include="*.py"` |

Add to weaknesses: "Pervasive silent exception handling. 66 occurrences of `except Exception:` across 31 files in the committed codebase. The worst offenders: `cli/main.py` (13), `knowledge/context_compiler.py` (6), `evaluation/evaluator.py` (5), `knowledge/store.py` (4)."

### B5. Maintainability Score (Executive Summary table)

| Field | v1.2.0 Says | v1.2.1 Corrects To | Rationale |
|-------|-------------|---------------------|-----------|
| Maintainability | 8.2 | **7.5** | 22 modules increase surface area; 66 silent exception handlers; untested replay path with verified defect |

### B6. Production Readiness Score (Executive Summary table)

| Field | v1.2.0 Says | v1.2.1 Corrects To | Rationale |
|-------|-------------|---------------------|-----------|
| Production Readiness | 4.0 | **4.5** | Minor increase justified by existing `projections/service.py` service layer (even though unwired), `diagnostics/doctor.py` health checks, and CI rigor; but still limited by auth/observability gaps |

---

## C. Wording Corrections

### C1. SchemaPolicy Description (§1.1)

**v1.2.0:** "`SchemaPolicy` is a `@dataclass(frozen=True)` with a single data field `_schemas` plus six methods (`latest_version`, `schema`, `migration_path`, `is_current`, `can_resolve`, `event_types`) containing real lookup/comparison logic; its docstring says 'no executable code'"

**v1.2.1:** Remove the phrase "its docstring says 'no executable code'" — the docstring describes the *field* (`_schemas`), not the class. The class has six methods with real logic. The v1.2.0 text already corrects this in the ▸ Correction note; v1.2.1 simply removes the confusing original phrasing.

### C2. ReplayService (§6 Application Service Recommendation)

**v1.2.0:** "Introduce an Application Service layer"

**v1.2.1:** "A `ReplayService` class exists in `projections/service.py` as an unused foundation. Extend and integrate it into a full Application Service layer rather than creating one from scratch."

### C3. compile_at_sequence() (§1.7, §4.2)

**v1.2.0:** "compile_at_sequence() is a partial implementation, not a stub" — this is correct and should be kept.

**v1.2.1:** No change needed. The v1.2.0 description is accurate.

---

## D. New Section: Runtime Defect

### Add §1.8: Runtime Defect: EventRecord Schema Version Mismatch

Insert after §1.7 (Weaknesses) and before §1.9 (Future scaling limitations).

**Evidence summary:**

`EventRecord` (`schema/events.py:142-196`) is a `@dataclass` with exactly 10 fields: `event_sequence`, `id`, `project_id`, `stream_id`, `version`, `event_type`, `metadata`, `payload`, `parent_id`, `recorded_at`. There is no `schema_version` field. No `__post_init__`, `__setattr__`, or `__getattr__` override exists.

Both database stores construct `EventRecord` with these 10 fields:
- `sqlite_store.py:113-124` (append_event), `sqlite_store.py:254-265` (_row_to_record)
- `postgres_store.py:72-83` (append_event), `postgres_store.py:211-222` (_row_to_record)

Neither the SQLite table schema (`sqlite_store.py:38-50`) nor the Postgres INSERT (`postgres_store.py:48-69`) includes a `schema_version` column.

However, the schema evolution machinery references `event.schema_version` in committed code:

| Location | Code | Failure |
|---|---|---|
| `policy.py:65` | `event.schema_version == self.latest_version(...)` | `AttributeError` |
| `policy.py:79` | `current = event.schema_version` | `AttributeError` |
| `resolver.py:35,40` | `f"...{event.schema_version}..."` / `current_version = event.schema_version` | `AttributeError` |
| `resolver.py:62` | `EventRecord(..., schema_version=current_version)` | `TypeError: unexpected keyword argument` |

**Entry point:** `projections/pipeline.py:43` calls `self._resolver.resolve(event)`, which calls `self._policy.is_current(event)` at line 30, hitting `event.schema_version` at `policy.py:65`.

**Why it hasn't surfaced:** The replay path is **completely untested** — grep for `ReplayResolver`, `ReplayPipeline`, `resolve.*event`, and `schema_version` across all test files returns zero matches.

**Root cause:** `EventRecord` is a storage-envelope type (event_sequence, id, type, payload, etc.) while `schema_version` appears to be a property the schema-evolution code expects on domain events. The resolver/policy code was written to operate on events that carry their schema version, but the envelope type that stores return doesn't carry it.

**Suggested fix:** Add `schema_version: int = 1` to `EventRecord` (defaulting to 1 for backward compatibility with existing events), and update `_row_to_record()` in both stores to read `schema_version` from the database row (or default to 1 if the column doesn't exist yet).

**Severity:** Hard crash (`AttributeError`/`TypeError`) on any call to `ReplayPipeline.process()` or `ReplayPipeline.run()` with a real `EventRecord` from either store. All committed code paths that exercise schema evolution are affected.

---

## E. Revised Scorecard

| Dimension | v1.2.0 | v1.2.1 | Change |
|-----------|--------|--------|--------|
| Overall Architecture | 8.5 | **8.5** | No change |
| Innovation | 8.5 | **8.5** | No change |
| Maintainability | 8.2 | **7.5** | ↓ — Larger codebase surface, untested defect, silent exceptions |
| Scalability (architectural) | 7.0 | **7.0** | No change |
| Scalability (current) | 4.5 | **4.5** | No change |
| Production Readiness | 4.0 | **4.5** | ↑ — Existing service layer and diagnostics infrastructure |

---

## F. Revised Roadmap

### P0 — Critical (Must Fix)

1. **Fix EventRecord schema_version defect** (§1.8) — Add `schema_version: int = 1` field to `EventRecord`, update both store `_row_to_record()` methods, add tests for `ReplayResolver.resolve()` and `SchemaPolicy.is_current()`.
2. **Add structured logging to silent exception paths** — Especially `db/event_store.py:64-65` and the 65 other `except Exception:` sites.

### P1 — High Impact (Should Fix Soon)

3. **Extend ReplayService into a full Application Service layer** — `projections/service.py` already provides the foundation. Extend to cover event appending, context compilation, and graph queries.
4. **Wire a real `semantic_provider`** — The RRF blending interface exists and is correct. Implement one embedding backend behind it.
5. **Implement snapshot store** — Per the existing design sketch in `cognitive_head/snapshot.py`.

### P2 — Medium-term (v1.4–v1.5)

6. **Add authentication/authorization to MCP server** — Currently zero auth/authz.
7. **Decompose `cli/main.py`** — 1,930 lines / 59 subcommands.
8. **Document and implement WAL-checkpoint/backup** for SQLite backend.

### P3 — Long-term (v2.0+)

9. **Async/eventually-consistent projections** for heavier projections.
10. **Distributed storage backend** — BaseEventStore abstraction supports this.
11. **Framework-native adapters** — LangGraph, CrewAI, AutoGen integration.

---

*End of patch. Apply these changes to the v1.2.0 review to produce v1.2.1.*
