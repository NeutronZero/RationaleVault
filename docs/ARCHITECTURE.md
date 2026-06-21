# Relay Architecture

## Overview

Relay is a persistent, event-sourced project memory layer. It allows any AI agent — Claude, ChatGPT, Hermes, Cursor, OpenCode — to resume work on a project with full context continuity, without manual summarization.

## Core Principle

> Every fact, decision, task, and relationship is derived from an immutable event ledger.
> State is never stored directly — always compiled from events.

This is the same design principle used by event sourcing in production systems, applied to the problem of AI agent context continuity.

## System Components

```
┌─────────────────────────────────────────────────────────┐
│                     Relay V1 Stack                       │
├─────────────────────────────────────────────────────────┤
│  AgentCompilers          relay/compilers/               │
│  (ClaudeCompiler, ...)   Format state for each agent    │
├─────────────────────────────────────────────────────────┤
│  Cognitive Head          relay/cognitive_head/           │
│  (compile_cognitive_head) Pure replay from events       │
│  (reducers)              State folds — no I/O           │
│  (SnapshotStore)         Placeholder for future caching │
├─────────────────────────────────────────────────────────┤
│  Event Store             relay/db/event_store.py        │
│  (append_event)          Immutable append-only ledger   │
│  (get_project_stream)    Replay by event_sequence ASC   │
├─────────────────────────────────────────────────────────┤
│  PostgreSQL 17           docker/postgres/               │
│  (relay_events table)    uuid-ossp, BIGSERIAL           │
└─────────────────────────────────────────────────────────┘
```

## Event Ordering

`event_sequence` (BIGSERIAL, assigned by PostgreSQL) is the **only** authoritative replay ordering key.

```sql
-- Always:
SELECT ... FROM relay_events WHERE project_id = %s ORDER BY event_sequence ASC

-- Never:
ORDER BY version          -- concurrency guard only
ORDER BY recorded_at      -- wall clock, not causal order
```

Per-project `version` exists only for optimistic concurrency control via `UNIQUE (project_id, version)`. Application code assigns `version` under a PostgreSQL advisory lock.

## Project Bootstrap Requirement

Every project stream **must** begin with:

```
PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED
```

`compile_cognitive_head()` raises `MissingProjectBootstrapError` if any of these are absent.

## Data Flow

```
Agent Action
     ↓
EventStore.append_event()
     ↓
relay_events (PostgreSQL)
     ↓
EventStore.get_project_stream()  [ORDER BY event_sequence ASC]
     ↓
Reducers (pure folds — no I/O)
  ProjectReducer → ProjectState
  TaskReducer    → dict[task_id, TaskState]
  DecisionReducer → dict[decision_id, DecisionState]
  QuestionReducer → dict[question_id, QuestionState]
     ↓
compile_cognitive_head()
  → derives active_tasks, active_decisions, open_questions, blockers
  → returns CognitiveHead
     ↓
AgentCompiler.compile(head)
  → formatted context string for target agent
     ↓
Agent resumes work
```

## Technology Decisions

| Decision | Rationale |
|----------|-----------|
| Python 3.12 | Matches RTOS-Graph-RAG platform; modern type hints |
| psycopg3 (sync) | Low-volume local workload; async adds complexity without benefit |
| No ORM | Event ledger must be fully auditable; every query explicit |
| No Alembic | Plain SQL + init_db.py sufficient for V1; introduce later |
| PostgreSQL 17 | Reliable, uuid-ossp, JSONB, BIGSERIAL, advisory locks |
| Docker Compose | Reproducible local environment; no bare-metal setup required |

## Sprint Plan

| Sprint | Goal | Key Deliverable |
|--------|------|-----------------|
| A | Event Ledger | `append_event`, `replay_stream`, 1000-event test |
| B | Cognitive Head + Compiler | `compile_cognitive_head`, `ClaudeCompiler` |
| C | Real Experiment | Claude → Relay → ChatGPT → Relay → Hermes |
| D | Based on failures | Add only what Sprint C failures demand |

## What Relay V1 Does NOT Build

By design, Relay V1 defers until Sprint D or later:

- Knowledge Compiler (R3)
- Context Assembly Planner / Graph-RAG retrieval (R4)
- Validation Engine (R6)
- Audit Dashboard (R7)
- Reflection Engine (R8)
- Embeddings, vector search
- Cursor / Hermes / ChatGPT / OpenCode specific compilers

These are added only when real Sprint C failures demonstrate they are needed.
