# Timeline Extension Architecture

This projection exists to maintain the current state of tasks in a workspace, tracking their lifecycle from creation to completion.

## Consumed Events
- `TaskCreated`
- `TaskAssigned`
- `TaskCompleted`

## Produces State
- `TimelineExtensionState` (A dictionary of task ID to `Task` objects)

## Runtime
- Exposes `get_task` and `list_tasks` methods for other projections/skills to query current tasks.
- Read-only queries, strictly deterministic.

## Architectural Invariants
- Reducers never perform I/O.
- Replay must remain deterministic.
- State is immutable during reduction.

## Dependencies
- None.
