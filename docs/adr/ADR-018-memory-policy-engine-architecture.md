# ADR-018: Memory Policy Engine Architecture

**Status**: Accepted
**Date**: 2026-06-26
**Deciders**: RationaleVault team
**Technical Story**: How should memory behavior be configured without changing agent code?

---

## Context

The MemoryBroker (v2.6) bridges the Agent Runtime with the memory substrate. But the broker's behavior was hardcoded:
- Retrieval always used hybrid strategy
- Caching was always enabled with fixed TTL
- Provenance was always full-depth
- Write validation was always schema + importance
- Deduplication was always exact match

Different scenarios need different behaviors:
- High-throughput scenarios need relaxed dedup and aggressive caching
- Audit-critical scenarios need full provenance and strict validation
- Multi-agent scenarios need configurable cache invalidation
- Research scenarios need graph-based retrieval

## Decision

Introduce a **Memory Policy Engine** with five orthogonal policy dimensions.

### Architecture

```
MemoryBroker
    ↕
MemoryPolicyEngine
    ↕
MemoryPolicy (composite)
    ├── RetrievalPolicy
    ├── CachePolicy
    ├── ProvenancePolicy
    ├── WritePolicy
    └── DedupPolicy
```

### Policy Dimensions

**1. RetrievalPolicy** — How memories are found and scored
- Strategy: LEXICAL, SEMANTIC, HYBRID, GRAPH, ADAPTIVE
- Type weights per memory type
- Importance boosts and lifecycle penalties
- Recency decay configuration

**2. CachePolicy** — When cached contexts are valid
- Invalidation: TTL, LRU, EVENT_DRIVEN, MANUAL
- TTL and max age configuration
- Entry limits

**3. ProvenancePolicy** — How deep provenance chains are traced
- Depth: NONE, SHALLOW, FULL, COMPLETE
- Required source types
- Chain length bounds

**4. WritePolicy** — How write requests are validated
- Validation: NONE, SCHEMA, IMPORTANCE, FULL
- Importance thresholds
- Required fields (project_id, tags)
- Content length limits
- Memory type allowlists

**5. DedupPolicy** — How duplicate memories are handled
- Strategy: EXACT, SIMILARITY, SEMANTIC, NONE
- Similarity threshold for Jaccard matching
- Merge behavior on dedup

### Preset Policies

Three built-in presets cover common scenarios:

| Preset | Behavior |
|--------|----------|
| `default` | Conservative: hybrid retrieval, TTL caching, full provenance, full validation, exact dedup |
| `aggressive` | High-throughput: 20 results, 600s TTL, 500 entries, similarity dedup at 0.5 |
| `strict` | Audit-critical: complete provenance, project_id required, tags required, similarity dedup at 0.25 |

### Design Rules

1. **Policies are immutable** — no mutation after construction
2. **Policies compose** — MemoryPolicy = 5 dimensions
3. **Default is safe** — default policy works for all scenarios
4. **Agent-controlled** — agents select policies, engine enforces them
5. **Engine is stateless** — all state lives in policies

## Consequences

### Positive
- Memory behavior configurable without code changes
- Three presets cover common scenarios
- Policies compose cleanly (5 orthogonal dimensions)
- Engine is stateless and testable
- Future policies can be added without breaking existing code

### Negative
- One more abstraction layer
- Policy selection requires agent awareness

## Alternatives Considered

### 1. Hardcoded broker behavior
**Rejected**: Different scenarios need different behaviors; one size doesn't fit all.

### 2. Configuration files
**Rejected**: Configuration is runtime state, not file state; policies should be typed and composable.

### 3. Strategy pattern per behavior
**Rejected**: Five orthogonal dimensions don't fit a single strategy interface.

## Relationships

- Depends on: Memory Integration (v2.6)
- Extends: MemoryBroker behavior
- Frozen: v2.7 (Memory Policy Engine Freeze)

---

*ADR-018 — Accepted 2026-06-26*
