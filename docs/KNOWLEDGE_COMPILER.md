# Relay Knowledge Compiler

## Status: DEFERRED to Sprint D

The Knowledge Compiler (Phase R3) is not built in V1.

It will be implemented only if Sprint C failures demonstrate that knowledge persistence is needed.

---

## What It Will Do

The Knowledge Compiler transforms events into durable, structured facts:

```
Event
  ↓
Candidate Fact
  ↓
Validation (confidence, maturity)
  ↓
Canonical Fact
  ↓
EntityRepository + FactRepository + RelationshipRepository
```

## Knowledge Stubs (V1)

V1 includes `FACT_RECORDED` and `RELATIONSHIP_CREATED` event types.

These events are stored in the ledger but not compiled into structured knowledge in V1.
They exist as storage hooks so Sprint C data is available for Sprint D.

```python
store.append_event(pid, "knowledge", EventType.FACT_RECORDED, {
    "fact_id": "fact_01",
    "content": "PostgreSQL advisory locks are sufficient at V1 scale.",
    "confidence": "agent_claim",
    "source": "implementation_review",
}, meta)
```

## Confidence Levels (Future)

```
agent_claim         ← single agent asserts
multi_agent_consensus ← multiple agents agree
human_confirmed     ← human verified
implemented         ← reflected in working code
```

## Maturity Pipeline (Future)

```
candidate → observed → confirmed → canonical → historical → archived
```

## When to Build This

Build the Knowledge Compiler when Sprint C shows:
- Critical facts are being re-derived by each incoming agent
- Architecture decisions are not persisting across handoffs despite the Claude Compiler
- The Context Block is growing too large for the token budget

Until then, `FACT_RECORDED` events accumulate and can be extracted later.
