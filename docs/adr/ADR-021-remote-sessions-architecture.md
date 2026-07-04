# ADR-021: Remote Sessions Architecture

**Status:** Accepted  
**Date:** 2026-06-28  
**Version:** v3.0  
**Decision Makers:** RationaleVault Architecture  
**Related:** ADR-013 (Agent Runtime), ADR-014 (Transport/Vendor Separation)

## Context

The platform has 17 architectural layers frozen through v2.9. Every layer assumes a single runtime process. H7 introduces the contracts for distributed cognition: multiple runtime nodes sharing workspaces, agents migrating between nodes, and telemetry aggregated across nodes.

The key architectural constraint: **the Event Ledger remains the only source of truth. Nodes are execution environments, not authorities.**

## Decision

**Remote Sessions define identity and movement, not consistency semantics.**

H7 is contracts-only — no networking, no actual distributed coordination. It defines:
- Runtime node identity (RuntimeNode)
- Operational health (NodeHealth, separate from identity)
- Session distribution across nodes (RemoteSession)
- Session migration records (SessionHandoff)
- Node registry (NodeRegistry)
- Cross-node telemetry aggregation (CrossNodeTelemetry)

### Key Principles

1. **Event Ledger as source of truth** — workspace state derives from events, not from node synchronization
2. **Identity ≠ health** — RuntimeNode (who exists) is separate from NodeHealth (how they perform)
3. **Movement, not consensus** — H7 defines session transfer, not conflict resolution
4. **Immutable handoff records** — every migration attempt produces an immutable record; retries produce new records
5. **Pluggable aggregation** — telemetry aggregation strategies are extensible components
6. **Reuse existing capabilities** — distributed capabilities extend the existing Capability enum

### Architecture

```
Single Runtime                    Distributed Runtime
─────────────                    ───────────────────
AgentSession (AGS-)              RemoteSession (RSES-RS-)
    ↓                                ↓
RuntimeContext (RTC-)             RuntimeNode (RSES-NODE-)
    ↓                                ↓
Workspace (WS-)                  NodeRegistry (RSES-NR-)
                                     ↓
                                 CrossNodeTelemetry (RSES-XTEL-)
```

### Contracts

| Contract | Prefix | Purpose |
|----------|--------|---------|
| RuntimeNode | RSES-NODE- | Identity of a runtime instance |
| NodeHealth | — | Operational health (separate from identity) |
| RemoteSession | RSES-RS- | Agent session spanning multiple nodes |
| SessionHandoff | RSES-HO- | Immutable record of session transfer |
| NodeRegistry | RSES-NR- | Registry of all known runtime nodes |
| CrossNodeTelemetry | RSES-XTEL- | Telemetry aggregated from multiple nodes |

### Handoff State Machine

```
INITIATED → IN_PROGRESS → COMPLETED
                       → FAILED
```

Failed handoffs produce new SessionHandoff records, not state mutations. This keeps every migration attempt immutable and auditable.

### Telemetry Aggregation

Aggregation strategies are pluggable (following the DimensionEstimator pattern):

| Strategy | Method |
|----------|--------|
| AverageAggregation | AVERAGE |
| SumAggregation | SUM |
| MinAggregation | MIN |
| MaxAggregation | MAX |
| P95Aggregation | P95 |

New strategies (weighted average, EWMA, median) can be added without modifying the aggregator.

### Distributed Capabilities

Five new capabilities extend the existing Capability enum:
- `CAN_HOST_REMOTE` — node can host remote sessions
- `CAN_MIGRATE` — agent can be migrated between nodes
- `CAN_AGGREGATE_TELEMETRY` — node can aggregate cross-node telemetry
- `CAN_SIMULATE` — node can run policy simulations
- `CAN_VIEW_POLICY` — agent can view adaptive policies

## Consequences

### Positive
- Clean extension of existing architecture (no breaking changes)
- Event Ledger remains single source of truth
- Identity and health evolve independently
- Handoff records are immutable and auditable
- Aggregation is extensible

### Negative
- No actual networking or distributed coordination
- No conflict resolution (deferred to later milestone)
- No cross-node memory (deferred to H8)

## Alternatives Considered

1. **Add ROLLBACK to handoff state** — Rejected: retries as new records are simpler and more auditable
2. **Define conflict resolution in H7** — Rejected: would turn H7 into a distributed database
3. **Separate distributed capability hierarchy** — Rejected: reuse existing Capability enum for uniformity
4. **Cross-node memory in H7** — Rejected: requires locality, routing, consistency, caching decisions (H8)

## Freeze

Frozen at v3.0:
- RuntimeNode, NodeHealth, RemoteSession, SessionHandoff, NodeRegistry
- CrossNodeTelemetry, AggregationStrategy protocol
- NodeTelemetryAggregator
- RSES identifier prefix family
- Distributed capabilities (5 new values in Capability enum)
