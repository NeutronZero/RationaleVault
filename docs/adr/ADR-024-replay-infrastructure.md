# ADR-024: Replay Infrastructure

> **Status:** Accepted
> **Date:** 2026-06-29
> **Deciders:** Chief Architect, User
> **Relates to:** F13 (Replay Infrastructure)
>
> ---
>
> ## Context
>
> Now that events carry `schema_version`, we must make the replay engine version-aware. This must be done without polluting the projection layer or event store with upcasting/resolving logic.
>
> ---
>
> ## Decision
>
> 1. Introduce `ReplayResolver` (replacing the temporary `SchemaResolver`) to sit between the raw event stream from storage and the projection engine.
> 2. Implement `UnknownSchemaError` handling in `ReplayResolver` for unsupported versions.
> 3. Introduce `ReplayContext` to encapsulate parameters for replay execution, and have it own the `ReplayResolver`.
> 4. Ensure projections are decoupled from schema mapping/resolving by having the replay interface / pipeline apply the resolver and context filtering before feeding events to the projections.
>
> ---
>
> ## Consequences
>
> ### Positive
> - Decouples projections from the evolution of event payload schemas (satisfying T2).
> - Establishes `ReplayContext` as the single conceptual hub representing how replay should be interpreted (schema version, sequence limits, compatibility, etc.).
>
> ### Negative
> - Adds a resolver step in the replay/read pipeline.
>
> ---
>
> ## Theorem Traceability
>
> - **Implements:**
>   - T3 Replay Evolution
> - **Preserves:**
>   - T1 Replay Equivalence
>   - T12 Interpretive Locality
>
> ---
>
> ## References
>
> - [resolver.py](file:///c:/Projects/Relay/rationalevault/schema/resolver.py)
> - [context.py](file:///c:/Projects/Relay/rationalevault/projections/context.py)
