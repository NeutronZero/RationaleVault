# Relay Event Ledger

## Purpose

The Event Ledger is the foundation of Relay. It is a PostgreSQL-backed, append-only table of events. Every fact, task, decision, and question in Relay is ultimately derived from events in this table.

## Immutability Contract

**Never UPDATE or DELETE rows in `relay_events`.**

The ledger is append-only by design. If a fact changes, a new event is appended. Historical events are never modified. This ensures perfect reproducibility: any past state can be reconstructed by replaying events up to a given `event_sequence`.

## Schema

```sql
CREATE TABLE relay_events (
    event_sequence  BIGSERIAL NOT NULL,           -- PRIMARY ordering key
    id              UUID NOT NULL DEFAULT uuid_generate_v4(),
    project_id      UUID NOT NULL,
    stream_id       TEXT NOT NULL DEFAULT 'main',
    version         BIGINT NOT NULL,              -- concurrency guard only
    event_type      TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    payload         JSONB NOT NULL DEFAULT '{}',
    parent_id       UUID REFERENCES relay_events(id),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (event_sequence),
    UNIQUE (id),
    UNIQUE (project_id, version)
);
```

## Ordering Guarantee

`event_sequence` is a PostgreSQL `BIGSERIAL`. It is assigned atomically by the database, never by application code. This guarantees global monotonic ordering across all projects.

**All replay queries must use:**
```sql
ORDER BY event_sequence ASC
```

The `version` field is a per-project monotonic counter. It is assigned by the application under a PostgreSQL advisory lock. It exists only for the `UNIQUE (project_id, version)` concurrency guard. **Never use `version` for replay ordering.**

## Concurrency Model

Multi-agent writes to the same project are serialized via PostgreSQL advisory locks:

```python
lock_key = UUID(project_id).int & 0x7FFFFFFFFFFFFFFF
cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
```

This is a transaction-scoped lock, so it is automatically released when the transaction commits or rolls back. Lock scope is per-project: concurrent writes to different projects do not block each other.

## Event Structure

Every event follows the same envelope:

```json
{
  "event_sequence": 42,
  "id": "uuid",
  "project_id": "uuid",
  "stream_id": "tasks",
  "version": 15,
  "event_type": "TASK_CREATED",
  "metadata": {
    "actor": "Claude",
    "source": "ClaudeCompiler",
    "correlation_id": "uuid",
    "session_id": "uuid"
  },
  "payload": {
    "task_id": "task_01",
    "title": "Implement EventStore"
  },
  "parent_id": null,
  "recorded_at": "2026-06-21T18:30:00Z"
}
```

## Sub-streams

The `stream_id` field allows events to be grouped logically within a project:

| stream_id | Contents |
|-----------|----------|
| `main` | Project lifecycle events |
| `tasks` | Task events |
| `decisions` | Decision events |
| `questions` | Question events |
| `knowledge` | Fact and relationship stubs |
| `metrics` | Handoff metric records |

**Reducers load ALL streams.** Sub-streams exist for targeted queries only. Never use `stream_id` as a replay filter in reducers.

## Bootstrap Requirement

Every project stream must begin with these three events in order before any other event type:

```
PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED
```

`compile_cognitive_head()` validates this and raises `MissingProjectBootstrapError` if violated.

## APIs

```python
store = EventStore()

# Append an event
record = store.append_event(
    project_id=pid,
    stream_id="tasks",
    event_type=EventType.TASK_CREATED,
    payload={"task_id": "t1", "title": "Task"},
    metadata=EventMetadata(actor="Claude", source="manual"),
)

# Load all events for a project (for compile_cognitive_head)
events = store.get_project_stream(pid)

# Load incrementally (after a snapshot)
new_events = store.get_project_stream(pid, since_sequence=last_snapshot_seq)

# Stream events one at a time (large ledgers)
for event in store.replay_stream(pid):
    process(event)

# Load a specific sub-stream
decisions = store.get_stream(pid, "decisions")
```
