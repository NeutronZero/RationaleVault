# Extension Points

RationaleVault is designed to be highly extensible. However, to protect the core architecture from unnecessary coupling, we distinguish between **Stable** extension points and **Advanced** extension points.

## Stable Extension Points
Most contributors and feature developers should only ever need to interact with these extension points. They are fully supported, backward-compatible, and well-documented.

1. **Projection**
   - **What:** Derive new state from the event stream.
   - **Where:** `rationalevault/projections/`

2. **Runtime (Stateless Service)**
   - **What:** Filter, rank, or compute query results from projections.
   - **Where:** Domain-specific runtime modules (e.g., `rationalevault/governance/runtime.py`).

3. **Skill**
   - **What:** Allow the agent to interact with the outside world (I/O).
   - **Where:** `rationalevault/skills/`

4. **CLI Command**
   - **What:** Expose functionality to human users via the terminal.
   - **Where:** `rationalevault/cli/commands/`

5. **MCP Tool**
   - **What:** Expose functionality to AI agents via the Model Context Protocol.
   - **Where:** `rationalevault/mcp/tools.py`

---

## Advanced Extension Points
These extension points govern the lowest levels of the framework infrastructure. **Most developers should never need to modify these.** Extending them requires deep familiarity with the RationaleVault lifecycle, as mistakes here compromise determinism, scale, or storage integrity.

1. **Snapshot Policy**
   - **What:** Defines the heuristic rules for when a projection should be written to cold storage (e.g., every N events, or after X seconds).
   - **Where:** `rationalevault/cognitive_head/snapshot_policy.py`

2. **Storage Backend**
   - **What:** Implements `EventStore` or `SnapshotStore` for a new physical database (e.g., migrating from SQLite to Postgres).
   - **Where:** `rationalevault/db/`

3. **Replay Strategy**
   - **What:** Modifies how the Replay Engine batches and dispatches events to the Projection Platform.
   - **Where:** `rationalevault/cognitive_head/replay_engine.py`

4. **Projection Compiler**
   - **What:** Transforms Python type hints into the canonical Protobuf/JSON-schema for the event store.
   - **Where:** `rationalevault/projection_platform/compiler.py`

5. **Session Registry**
   - **What:** Manages the active, distributed tracking of agent sessions.
   - **Where:** `rationalevault/runtime/session_registry.py`
