# ADR-022: EventStore Purity

> **Status:** Accepted
> **Date:** 2026-06-29
> **Deciders:** Chief Architect, User
> **Relates to:** Design Philosophy, F11 (Runtime Integrity)
>
> ---
>
> ## Context
>
> Previously, `EventStore.append_event()` silently executed memory extraction and lifecycle transition routines. This created an implicit write side-effect inside the append-only ledger write path. This violated the following:
> - **T2 (Projection Purity):** A storage method that writes to another system (Memory Provider) as a side-effect is not pure.
> - **T1 (Replay Equivalence):** Replay of the event stream did not trigger memory extraction, leading to potential divergence between the event ledger and the memory corpus.
>
> ---
>
> ## Decision
>
> Remove all automatic memory emission and lifecycle transitions from `EventStore.append_event()`. The EventStore append operation is now a pure ledger insert.
>
> Any components requiring memory extraction (e.g. CLI, handoff suite, workspace services) must explicitly orchestrate the extraction and lifecycle transition using the returned `EventRecord`:
>
> ```python
> record = store.append_event(...)
> memories = extract_memories_from_event(record)
> if memories:
>     for m in memories:
>         provider.add_record(m)
> handle_lifecycle_transitions(record)
> ```
>
> ---
>
> ## Consequences
>
> ### Positive
> - Replay equivalence is preserved: the ledger is a pure, append-only source of truth.
> - Clear separation of concerns: writing to the ledger and extracting projections (like memories) are distinct steps.
> - Test predictability: tests no longer rely on silent side-effects of append.
>
> ### Negative
> - Callers must explicitly run extraction if they intend for events to generate memories at write time.
>
> ---
>
> ## Theorem Traceability
>
> - **Implements:**
>   - T1 Replay Equivalence
>   - T2 Projection Purity
> - **Preserves:**
>   - T11 Monotonic Understanding
> - **Does not affect:**
>   - T8 Evidence Accumulation
>   - T12 Interpretive Locality
>
> ---
>
> ## References
>
> - [event_store.py](file:///c:/Projects/Relay/rationalevault/db/event_store.py)
