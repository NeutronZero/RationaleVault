# ADR-023: Event Schema Versioning

> **Status:** Accepted
> **Date:** 2026-06-29
> **Deciders:** Chief Architect, User
> **Relates to:** F12 (Event Schema Versioning)
>
> ---
>
> ## Context
>
> To support long-term evolution of the platform without breaking historical replay determinism, events must carry explicit schema information rather than relying on implicit parser assumptions.
>
> ---
>
> ## Decision
>
> Introduce a `schema_version` field to `EventRecord` (defaulting to 1). Persist this version in SQLite and PostgreSQL stores.
>
> In accordance with Law 4 (Demonstrated Problem Before Frozen Contract), we defer building a full upcaster framework or compatibility branching mechanism until we encounter a schema version 2 event type in the codebase.
>
> ---
>
> ## Consequences
>
> ### Positive
> - Replay is future-proofed against schema changes.
> - Upcasting hook location is clear.
>
> ### Negative
> - Small storage overhead (one extra column).
>
> ---
>
> ## Theorem Traceability
>
> - **Implements:**
>   - T3 Replay Evolution
> - **Preserves:**
>   - T1 Replay Equivalence
>
> ---
>
> ## References
>
> - [events.py](file:///c:/Projects/Relay/rationalevault/schema/events.py)
