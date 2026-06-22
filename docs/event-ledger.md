# Relay Event Ledger

The immutable ledger is the source of truth for Relay.

---

## Event Schema

Every event is recorded with an envelope:
- `event_sequence` (global monotonic index)
- `id` (stable UUID)
- `project_id` (project UUID)
- `stream_id` (logical domain grouping)
- `version` (per-project optimistic lock key)
- `event_type` (e.g. `PROJECT_CREATED`)
- `metadata` (actor name, source tool, correlation IDs)
- `payload` (JSON body)
- `recorded_at` (UTC timestamp)

## Project Bootstrap

Every valid project stream must start with this sequence:
1. `PROJECT_CREATED`
2. `PROJECT_GOAL_SET`
3. `PROJECT_FOCUS_CHANGED`

If this sequence is violated, the cognitive head compiler raises a `MissingProjectBootstrapError`.
