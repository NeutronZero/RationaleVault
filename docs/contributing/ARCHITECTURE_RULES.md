# RationaleVault Architectural Rules

This document outlines the core architectural boundaries and rules that all contributors must follow when developing on RationaleVault. These rules are enforced programmatically by automated AST validation tests in CI.

---

## The Seven Rules

### 1. Stores Never Have Side Effects
`EventStore.append_event()` (and all database-specific store implementations) is a pure persistence layer. It must never trigger memory extraction, lifecycle transitions, projection updates, or policy decisions. These must be explicitly orchestrated by callers.

### 2. Replay Always Enters Through ReplayService
Compilers, builders, and orchestrators must never load raw events or invoke `ReplayPipeline` directly. All query and replay operations must go through `ReplayService` to ensure temporal and version constraints are applied uniformly.

### 3. Reducers and Projections are Pure Functions
Projections and state reducers must have no side effects and no external state dependencies (no clocks, random sources, network calls, or mutable repositories). The same event sequence must always produce the identical output.

### 4. Projections Never Import Replay Internals
Core projection classes (such as `BM25Projection`, `AliasProjection`, `GraphProjection`) must remain completely decoupled from schema evolution. They must never import `ReplayResolver`, `ReplayPipeline`, `UpcasterRegistry`, or `ReplayService`. They only accept `list[EventRecord]`.

### 5. Schema Evolution Uses Upcasters
When event payloads change incompatibly, do not modify historical event code or write migration scripts to alter existing database rows. Instead, register a version upcaster in `UpcasterRegistry` to transform payloads on-the-fly during replay.

### 6. New Abstractions Require Demonstrated Problems
Follow Law 4 (Demonstrated Problem Before Frozen Contract). Never design speculative interfaces or frameworks for "future use." Abstractions should only be introduced when the second concrete implementation instance actually exists in the codebase.

### 7. Boundaries Are Enforced by Tests
Architectural boundaries are not guidelines—they are assertions. Changes that violate dependency directions or import rules will fail the CI check (see `test_architecture_guards.py`).

---

*See also:*
* [`docs/adr/`](file:///c:/Projects/Relay/docs/adr/) — Architecture Decision Records
* `architectural_theorems.md` — The mathematical proof-sketch backing these rules
