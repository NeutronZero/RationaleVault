# RationaleVault Memory Layer

The Memory Layer converts ledger events into clean memory records.

---

## Memory Record Schema

- `id`: Stable reference string.
- `version`: Increments on content changes.
- `title`: Short summary.
- `content`: Memory details.
- `memory_type`: `DECISION`, `IMPLEMENTATION_NOTE`, etc.
- `importance`: `critical`, `high`, `medium`, `low`.
- `lifecycle_status`: `active`, `stale`, `superseded`, `archived`.
- `source_event_ids`: Parent events list.

## Lifecycle Management
When events such as `DECISION_SUPERSEDED` are appended, the memory manager automatically transitions old records to `superseded` or `archived` states, ensuring search results prioritize active context.
