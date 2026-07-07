# RationaleVault Architecture

RationaleVault is an event-sourced cognitive continuity and memory layer for multi-agent AI workflows. Its architecture is explicitly designed around the principles of Event Sourcing and Command Query Responsibility Segregation (CQRS).

## Core Philosophy

The system separates "what happened" (Events) from "what it means" (Projections).
- **The Ledger is immutable.** AI agents produce atomic events representing their reasoning, context, and decisions.
- **The Projections are ephemeral.** The current state of the system is derived by replaying these events through deterministic reducers.

This architecture enables:
1. **Cognitive Continuity:** A new agent can instantly understand the reasoning process of past agents by reading the projection state.
2. **Deterministic Replay:** The exact same event stream will always produce the exact same projection state.
3. **Decoupled Evolution:** New projections can be created to interpret historical events in entirely new ways, without altering the underlying ledger.

## Bounded Contexts

RationaleVault is divided into several strict bounded contexts:

### 1. Event Store (`rationalevault.db`)
The append-only ledger. It handles concurrent writes and atomic sequencing of events. Supports SQLite (local) and PostgreSQL (distributed).

### 2. Projection Platform (`rationalevault.projection_platform`)
The core infrastructure for defining, compiling, and replaying projections. It enforces deterministic reduction and snapshot invalidation.

### 3. Cognitive Head (`rationalevault.cognitive_head`)
The most complex projection suite in the system. It builds a graph of beliefs, assessments, and decisions from the raw reasoning events, synthesizing them into actionable context for agents.

### 4. Runtimes (`rationalevault.runtime`, `rationalevault.mcp`)
The integration boundaries. The CLI provides human-centric management, while the MCP (Model Context Protocol) Server exposes tools and state to LLM clients dynamically.

## Code Constraints & Dependency Rules
- **Projections cannot mutate the event stream.** They are strictly read-only aggregations.
- **The CLI must remain declarative.** All business logic belongs in the projections and runtimes.
- **Cross-process locking** is handled explicitly when modifying SQLite memory bounds.

## Further Reading
- [Projection Lifecycle](projection-lifecycle.md)
- [Projection Archetypes](projection-archetypes.md)
- [Development & Error Policies](development.md)
