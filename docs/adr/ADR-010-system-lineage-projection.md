# ADR-010: System Lineage Projection

**Status:** Accepted  
**Date:** 2026-06-26  
**Deciders:** RationaleVault Architecture  
**Related:** ADR-008 (Reflection Events), ADR-009 (Knowledge Promotion Pipeline), v2.0 Cognitive Platform Freeze

---

## Context

Program F introduced seven interconnected subsystems (Reflection, Promotion, Validation, Advisory, Planner, Memory, Scheduler). Each subsystem tracks its own lineage internally, but nothing connects them.

Every object can answer "What produced me?" within its subsystem, but no object can answer "Why do I exist?" across the full cognitive loop.

## Decision

Implement `SystemLineageProjection` — a unified directed graph that connects all subsystems through typed edges.

### Graph Structure

```text
LineageNode (object_id, subsystem)
    ↓  EdgeType
LineageNode
```

### Node Types

Every object in the system gets a `LineageNode` with:
- `LINNODE-[hash]` — deterministic ID
- `object_id` — the actual object ID (BEL-, DEC-, KNOW-, etc.)
- `subsystem` — which Program F subsystem owns this object

### Edge Types

| EdgeType | Meaning |
|----------|---------|
| `DERIVED_FROM` | General derivation |
| `CAUSED_BY` | Causal relationship |
| `PROMOTED_FROM` | Knowledge promotion |
| `VALIDATED_BY` | Knowledge validation |
| `EVOLVED_INTO` | Knowledge evolution |
| `EXECUTED_FOR` | Skill execution |
| `GENERATED_BY` | Artifact generation |
| `REFLECTED_IN` | Reflection reference |
| `ADVISED_BY` | AI advisory |
| `ADJUSTED_BY` | Planner adjustment |
| `TRANSITIONED_VIA` | Memory lifecycle |
| `SCHEDULED_BY` | Cognitive scheduling |

### Query API

```python
projection.why_exists("KNOW-001")
# → ["REFL-001", "LEARN-001", "BEL-001", "EVT-001"]

projection.full_lineage_path("KNOW-001")
# → ["KNOW-001", "REFL-001", "LEARN-001", "BEL-001", "EVT-001"]

projection.ancestors("KNOW-001")
# → [all upstream LINNODE IDs]

projection.descendants("EVT-001")
# → [all downstream LINNODE IDs]
```

## Consequences

### Positive
- Any object can answer "Why do I exist?" with a single API call.
- Debugging and auditing become trivial — full lineage is one graph traversal.
- Visualization tools can render the complete cognitive loop.
- Replay verification can check lineage integrity.

### Negative
- Adds a new projection that must be kept in sync with all subsystems.
- Graph traversal has O(V+E) cost per query.

### Mitigations
- Deterministic ID generation ensures consistency.
- Append-only edges — never removed, only added.
- Graph is small (hundreds of nodes, not millions).

## Alternatives Considered

### 1. Decentralized Lineage (status quo)
Each subsystem tracks its own lineage. No unified view.
- Rejected: cannot answer cross-subsystem questions.

### 2. Event-Based Reconstruction
Reconstruct lineage by replaying all events.
- Rejected: expensive at query time. Pre-computed graph is better.

### 3. External Graph Database
Store lineage in Neo4j or similar.
- Rejected: adds external dependency. In-memory graph is sufficient for current scale.

## Freeze Level Impact

**L1 Freeze (v2.0):**
- `LineageNode`, `LineageEdge`, `SystemLineageProjection`
- `EdgeType`, `NodeSubsystem` enums
- Query methods: `why_exists`, `full_lineage_path`, `ancestors`, `descendants`

## References

- `rationalevault/knowledge/system_lineage.py` — Implementation
- `tests/unit/test_system_lineage.py` — 16 tests
- `tests/unit/test_e2e_cognitive_loop.py` — 8 integration tests
- `docs/v2.0_cognitive_platform_freeze.md` — Platform freeze document
