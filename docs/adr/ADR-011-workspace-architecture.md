# ADR-011: Workspace Architecture

**Date:** 2026-06-26
**Status:** Accepted
**Supersedes:** N/A

## Context

RationaleVault needs a public-facing interface for human and AI agents to interact with the cognitive substrate. The internal cognitive loop (Reflection → Knowledge → Validation → Advisory → Planner → Memory → Scheduler) is complete, but there is no structured way for agents to join, observe, and resume work in a workspace.

## Decision

Introduce a Workspace subsystem as the primary interface, consisting of:

1. **Contracts (G0):** Five frozen dataclasses (Workspace, Snapshot, Session, Context, Package) with typed IDs and event payloads.
2. **Projection (G1):** `WorkspaceStateProjection` answers "What is happening right now?" by aggregating decisions, executions, reflections, knowledge, promotions, planner, and scheduler state.
3. **Service (G2):** Deterministic service layer with `open`, `resume`, `pause`, `snapshot`, `diff`, `export`, `merge` — all pure functions returning `(domain_object, event_payload)` tuples.
4. **Context Compiler (G3):** Bridges `WorkspaceState` → `WorkspaceContext` for a specific agent.
5. **Continuation Engine (G4):** Orchestrates the full resume pipeline: `WorkspaceState → Context → Package`.
6. **Multi-Agent (G5):** Session management with role-based access (PRIMARY, ADVISOR, OBSERVER).

## Rationale

- **Workspace = public face:** Agents interact only through the workspace, never directly with internal subsystems.
- **No I/O in projection/service:** Enables deterministic testing, replay, and offline analysis.
- **Event sourcing:** Every state change produces an event payload for ledger emission.
- **Frozen dataclasses:** Immutable objects prevent accidental mutation.
- **SHA-256 IDs:** Deterministic, deduplication-safe identifiers.
- **Role-based access:** PRIMARY reads/writes, ADVISOR suggests, OBSERVER reads.

## Consequences

- All workspace operations are pure functions — easy to test, hard to break.
- The workspace is the only surface that needs authentication/authorization.
- Internal cognitive loop remains decoupled from the workspace interface.
- Future extensions (G6 freeze, persistence, UI) build on stable contracts.
