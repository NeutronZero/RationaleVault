# Relay Evaluation Gates Reference

Every logical layer in Relay enforces quality thresholds and exit gates. During `relay evaluate` runs, these metrics are computed and checked against hard limits.

| Layer | Gate / Metric | Threshold | Purpose |
|---|---|---|---|
| **Memory** | Deduplication Rate | $\ge 1.0$ (No duplicates) | Prevents redundant cognitive entries in memory store |
| **Memory** | Provenance Rate | $\ge 1.0$ (100% Trace) | Ensures all memory records link back to source events |
| **Retrieval** | Keyword Precision | $\ge 0.70$ | Ensures retrieved records are relevant to query keywords |
| **Knowledge** | Density | $\ge 0.10$ | Ensures knowledge objects form a dense, meaningful network |
| **Knowledge** | Contradiction Gate | $0$ contradictions | Prevents contradictory facts from being active simultaneously |
| **Context** | Completeness | $\ge 0.67$ (2 of 3 sources) | Blends events, memories, and knowledge objects in context packages |
| **Context** | Source Traceability | $\ge 1.0$ (100% Trace) | Ensures all blended citations have valid parent event chains |
| **Context** | Blending Determinism | $1.0$ (100% Match) | Assures identical query parameters produce identical packages |
| **Context** | Compiler Latency | $\le 500.0\text{ ms}$ | Ensures context compilation executes within budget |
| **Context** | Redundancy | $\le 0.25$ | Limits duplicate info inside the compiled prompt |
| **Graph** | Node Coverage | $1.0$ (100%) | All active knowledge must project to graph nodes |
| **Graph** | Edge Coverage | $1.0$ (100%) | All valid knowledge relationships must project to graph edges |
| **Graph** | Referential Integrity | $1.0$ (100%) | No edges pointing to non-existent node IDs |
| **Graph** | Graph Determinism | $1.0$ (100% Match) | Rebuilding graph projects identical graph ID hash |
| **Release** | CLI Doctor Success | PASS | Validates databases, compilers, and active projection chain |
| **Release** | Examples Execution | PASS | Confirms basic_memory, knowledge_synthesis, and handoff pass |
