# Relay Cognitive Head

## What Is the Cognitive Head?

The Cognitive Head is the compiled current state of a project. It is Relay's equivalent of `git HEAD` — a snapshot of where the project is right now, derived entirely from the immutable event ledger.

Unlike `git HEAD`, the Cognitive Head contains *semantic* state:

- What tasks are active?
- What decisions have been accepted?
- What questions remain unresolved?
- What is blocked?

## Determinism Contract

```
Same events → Same Cognitive Head (always)
```

The compiler is a pure function. Given the same sequence of events, it always produces identical output. There is no randomness, no timestamps in the derived state, no external I/O.

This means:

- Any agent can independently verify the project state by replaying the ledger.
- Debugging is always possible: replay any point-in-time and inspect the resulting head.
- Multi-agent race conditions cannot corrupt the compiled state.

## Bootstrap Requirement

Every project stream **must** begin with:

```
PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED
```

`compile_cognitive_head()` raises `MissingProjectBootstrapError` if any of these events are missing. This prevents partially initialized heads.

## Reducers

State is derived by four pure reducers:

```
events: list[EventRecord]  (ORDER BY event_sequence ASC)
    ↓
ProjectReducer.reduce(events)   → ProjectState
TaskReducer.reduce(events)      → dict[task_id, TaskState]
DecisionReducer.reduce(events)  → dict[decision_id, DecisionState]
QuestionReducer.reduce(events)  → dict[question_id, QuestionState]
```

Each reducer is a simple fold over the event list. Unknown event types are silently ignored (forward compatibility). The reducer never calls the database.

## Derived State

After running reducers, the compiler derives:

| Derived | Source |
|---------|--------|
| `active_tasks` | tasks where `status != "completed"` |
| `active_decisions` | decisions where `status == "accepted"` |
| `open_questions` | questions where `status == "open"` |
| `blockers` | tasks blocked by open questions (both `task.blocked_by` and `question.blocks_task_ids` checked) |

### Priority Sort Order

Both `active_tasks` and `open_questions` are sorted:
```
critical → high → normal → low
```

## Output — CognitiveHead

```json
{
  "project_id": "uuid",
  "project_name": "Relay V1",
  "project_goal": "Build continuity...",
  "current_focus": "Sprint C: first handoff experiment",
  "ledger_version": 42,
  "compiled_at": "2026-06-21T18:30:00Z",

  "active_tasks": [
    { "task_id": "...", "title": "...", "priority": "high", ... }
  ],
  "active_decisions": [
    { "decision_id": "...", "title": "...", "rationale": "..." }
  ],
  "open_questions": [
    { "question_id": "...", "title": "...", "priority": "high", "blocks_task_ids": [...] }
  ],
  "blockers": [
    { "task_id": "...", "task_title": "...", "blocked_by_questions": ["q_01"] }
  ]
}
```

## Snapshot Store (V1 Placeholder)

In V1, every call to `compile_cognitive_head()` performs a full replay of the event ledger.

At V1 scale (local DB, hundreds of events), this is fast and correct.

The `SnapshotStore` interface is defined now so a future V2 implementation can be dropped in without changing the compiler API:

```python
snapshot = snapshot_store.load_latest_snapshot(project_id)  # → None in V1
if snapshot:
    # Apply only events after snapshot.sequence
    new_events = store.get_project_stream(project_id, since_sequence=snapshot.sequence)
    # ... apply new events to snapshot.head ...
else:
    # Full replay
    head = compile_cognitive_head(project_id)
```

Implement snapshots when `compile_cognitive_head()` takes more than ~500ms.

## API

```python
from relay.cognitive_head.compiler import compile_cognitive_head

head = compile_cognitive_head(project_id)

print(head.project_name)          # "Relay V1"
print(head.ledger_version)        # 42
print(len(head.active_tasks))     # 3
print(len(head.open_questions))   # 2
print(head.to_dict())             # JSON-serializable dict
```
