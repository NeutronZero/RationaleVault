# ADR-025: Governance Events Taxonomy

> **Status:** Accepted
> **Date:** 2026-06-29
> **Deciders:** Chief Architect, User
> **Relates to:** F14 (Versioned Interpretation)
>
> ---
>
> ## Context
>
> For interpretation shifts to be deterministic and explainable (T5 - Governance Traceability), every change to the rules of interpretation (reducers, DAG topologies, policy configurations, or event schema structures) must be event-sourced.
>
> Because these events represent modifications to the governing logic of the platform rather than domain observations (Reality events), they must follow a strict, stable taxonomy. To prevent an explosion of raw event type names, we must decouple the event envelope from the governance domains and actions.
>
> ---
>
> ## Decision
>
> 1. Introduce a single, unified event type: `GOVERNANCE_DECISION_RECORDED`.
> 
> 2. Define structured **Governance Domains** and **Governance Actions**:
>    - `GovernanceDomain` (Enum):
>      - `POLICY`: Changes to memory, adaptive, or simulation policy parameters.
>      - `PROJECTION`: Changes to projection DAG topologies or build priorities.
>      - `SCHEMA`: Changes to upcasters or payload schema mappings.
>    - `GovernanceAction` (Enum):
>      - `ADJUSTED`: Changes to configuration values or policy constants.
>      - `TOPOLOGY_CHANGED`: Shift in the active projection DAG layout.
>      - `MIGRATION_APPLIED`: Upcaster registration or migration activation.
>      - `DEPRECATED`: Marking a policy or schema version as deprecated.
>      - `DISABLED`: Turning off a specific projection or policy.
>
> 3. Standardize the payload structure via `GovernanceRecord`:
>    ```python
>    @dataclass(frozen=True)
>    class GovernanceRecord:
>        domain: GovernanceDomain
>        action: GovernanceAction
>        target: str                    # The specific policy key, projection name, or event type
>        previous_version: Optional[str] = None
>        new_version: Optional[str] = None
>        rationale: str
>        approved_by: Optional[str] = None
>        effective_sequence: int        # The event sequence number at which this change takes effect
>    ```
>
> 4. Defer counterfactual replay capability. Replay modes under F14 will be strictly limited to:
>    - `HISTORICAL`: Replaying events exactly as they occurred in reality.
>    - `INTERPRETIVE`: Replaying events through the lens of governance shifts.
>    - `CURRENT`: Running on the latest active policy rules.
>
> ---
>
> ## Consequences
>
> ### Positive
> - T5 (Governance Traceability) is satisfied. Any interpretation shift can be traced to a specific ledger transaction.
> - Avoids name explosion in the database storage layer. A single table column is used, and domain filtering happens inside the `InterpretiveContext` projection.
> - Evolving governance (e.g. deprecating a policy or disabling a projection) requires only adding an action to `GovernanceAction`, leaving database schemas unchanged.

### Designed Equivalence Status
The Interpretive replay pathway is fully operational. However, at Architecture v3, the `UpcasterRegistry` contains no production upcasters because only schema version 1 exists. Consequently, `CURRENT` and `INTERPRETIVE` modes are behaviorally equivalent until the first schema version bump (v2) occurs. This equivalence is intentional and keeps the codebase free of speculative migration logic.
>
> ### Negative
> - Queries filtering for specific governance changes must parse the `GovernanceRecord` JSON payload rather than relying on top-level SQL `event_type` filtering.
>
> ---
>
> ## Theorem Traceability
>
> - **Implements:**
>   - T5 Governance Traceability
>   - T6 InterpretiveContext Completeness
> - **Preserves:**
>   - T1 Replay Equivalence
>   - T13 Replay Transparency
