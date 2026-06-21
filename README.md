# Relay

**Event-sourced memory layer for multi-agent AI workflows.**

Relay allows any AI agent — Claude, ChatGPT, Hermes, Cursor, OpenCode — to resume work on a project with full context continuity, within 30 seconds, without manual summarization.

---

## Core Principle

> Every fact, decision, task, and relationship is derived from an immutable event ledger.
> State is never stored directly — always compiled from events.

```
Claude starts work
       ↓
    Relay
  (ledger grows)
       ↓
Claude exhausted
       ↓
  compile_cognitive_head()
       ↓
  ClaudeCompiler → Context Block
       ↓
ChatGPT resumes (no context lost)
       ↓
    Relay
       ↓
   Hermes resumes
```

---

## Quick Start

### 1. Start PostgreSQL

```bash
docker-compose -f docker/postgres/docker-compose.yml up -d
```

### 2. Install dependencies

```bash
pip install -e ".[dev]"
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env if needed (defaults match docker-compose)
```

### 4. Initialize the database

```bash
python scripts/init_db.py
```

### 5. Seed a demo project

```bash
python scripts/seed_demo.py
```

This creates 20+ realistic events and prints a **Relay Context Block** you can paste directly into Claude to begin Sprint C.

### 6. Run tests

```bash
# Pure unit tests (no database required)
pytest tests/unit/ -v

# Database tests (requires RELAY_DB_TEST_ENABLED=1 in .env)
set RELAY_DB_TEST_ENABLED=1
pytest tests/unit/ -v
```

---

## Architecture

```
relay/
├── schema/events.py          # Canonical event types + metadata envelope
├── db/
│   ├── connection.py         # psycopg3 connection management
│   └── event_store.py        # Immutable append-only ledger
├── cognitive_head/
│   ├── reducers.py           # Pure state reducers (no I/O)
│   ├── snapshot.py           # SnapshotStore interface (placeholder)
│   └── compiler.py           # compile_cognitive_head()
└── compilers/
    ├── base.py               # AgentCompiler ABC
    └── claude.py             # ClaudeCompiler
```

### Event Ordering Guarantee

`event_sequence` (BIGSERIAL) is the **only** authoritative replay order.

All reducers use `ORDER BY event_sequence ASC`. The `version` field exists only for optimistic concurrency control.

### Project Bootstrap Requirement

Every project stream **must** begin with:
```
PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED
```

`compile_cognitive_head()` raises `MissingProjectBootstrapError` if these events are absent.

---

## Sprint Plan

| Sprint | Goal | Status |
|--------|------|--------|
| A | Reliable Event Ledger | ✅ Built |
| B | Cognitive Head + Claude Compiler | ✅ Built |
| C | Real multi-agent handoff experiment | 🔲 Run |
| D | Based on Sprint C failures only | 🔲 TBD |

---

## First Experiment (Sprint C)

See [`examples/first_experiment.md`](examples/first_experiment.md) for the step-by-step guide to running the Claude → Relay → ChatGPT → Relay → Hermes handoff experiment.

Measure continuity with:
```bash
python scripts/handoff_metrics.py --project-id <UUID>
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| psycopg3 (sync) | Low-volume local workload; async complexity not justified in V1 |
| No ORM | Event ledger must be fully auditable; every query explicit |
| No Alembic | Plain SQL migrations are sufficient and simpler for V1 |
| event_sequence for ordering | Prevents subtle ordering bugs in concurrent multi-agent writes |
| SnapshotStore placeholder | Interface defined now; implemented when ledger reaches scale |
