# Choosing the Right Abstraction

RationaleVault offers several extension points. Choosing the correct one is the most important architectural decision you will make when adding a new feature.

Use the following heuristic guide to determine which abstraction your feature requires.

## Decision Matrix

| If your feature...                      | Build...                                     |
| --------------------------------------- | -------------------------------------------- |
| Persists an immutable fact that occurred| **Event** (in `schema/`)                       |
| Derives deterministic state from events | **Projection** (in `projections/`)             |
| Computes ephemeral query results        | **Runtime** (in `runtime/` or domain equivalent) |
| Performs external actions or I/O        | **Skill** (in `skills/`)                       |
| Exposes functionality to users          | **CLI / MCP Adapter**                        |

---

## 1. Events
**Use when:** Something undeniable has happened in the system that other components might care about in the future.
- **Example:** `TaskCompletedPayload`, `SessionAttachedPayload`
- **Rule:** Events are immutable historical facts. They describe *what* happened, not *what should happen*.

## 2. Projections
**Use when:** You need to answer a question by reading the event stream, and that answer must be perfectly reproducible.
- **Example:** `WorkspaceProjection`, `MemoryTimeline`
- **Rule:** Projections are **pure functions**. They read an event stream and produce a state. They *never* perform I/O, make network calls, or read other projections.

## 3. Runtimes (Stateless Services)
**Use when:** You need to query, filter, rank, or combine data from one or more projections to answer a specific user request at runtime.
- **Example:** `RecommendationRuntime`, `GovernanceRuntime`
- **Rule:** Runtimes are ephemeral and stateless. They compute answers on the fly and never mutate state directly.

## 4. Skills
**Use when:** An agent needs to perform an action that affects the outside world (e.g., executing code, modifying files, calling an API).
- **Example:** `BashExecutionSkill`, `FileWriteSkill`
- **Rule:** Skills are sandboxed, permissioned, and emit events detailing their results. They are the *only* place where non-deterministic actions and side-effects are permitted.

## 5. CLI & MCP Adapters
**Use when:** A human (CLI) or an agent (MCP) needs an interface to invoke your Runtime or Skill.
- **Example:** `rv doctor` (CLI), `read_file` (MCP)
- **Rule:** Adapters should contain **zero business logic**. They exclusively handle argument parsing, serialization, and calling the appropriate Runtime or Skill.
