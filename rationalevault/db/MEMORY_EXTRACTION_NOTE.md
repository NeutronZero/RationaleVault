# Memory Extraction is Orchestration, Not Persistence

**Status:** Architectural decision — ADR-023  
**Discovered:** Phase A implementation (Architecture v3 validation)

---

## The Separation

Memory extraction from events is **orchestration**. It is not a side effect of
persistence. These are two independent responsibilities:

```
append_event()
    │
    ▼
Event Ledger        ← pure persistence; no side effects

    │  (separate step, explicit caller)
    ▼

extract_memories_from_event(record)
    │
    ▼
MemoryBroker.record_memory()
    │
    ▼
Memory Provider     ← separate persistence target
```

## What This Means in Practice

**EventStore.append_event() is a pure function.** It writes one record to the
ledger and returns it. It does not call any broker, provider, extractor, or
lifecycle function. It has no knowledge of the memory layer.

**Callers that need memory extraction must be explicit about it.** The pattern is:

```python
record = store.append_event(...)
memories = extract_memories_from_event(record)
if memories:
    provider = get_memory_provider()
    for m in memories:
        provider.add_record(m)
handle_lifecycle_transitions(record)
```

Or, for callers that always want extraction, wrap this in a helper.

## Why This Matters

Before ADR-023, EventStore silently called the extractor on every append.
This had several consequences:

1. **Replay was broken by design.** Replaying the event stream would not
   re-extract memories, because extraction happened at write time via a side
   effect. The Event Ledger and the Memory layer could diverge invisibly.

2. **Testing was unreliable.** Tests that appended events and then queried
   memories were depending on a side effect they could not observe or control.

3. **The dependency direction was inverted.** The persistence layer (EventStore)
   was importing from the orchestration layer (extractor, provider, lifecycle).
   The correct direction is the opposite.

## The Theorem Basis

This separation is required by **T2 (Projection Purity)**:

> A method that writes to the memory provider as a side effect of writing to
> the Event Ledger is not a pure function. It cannot satisfy replay equivalence
> because replaying the event does not reproduce the side effect.

## What to Never Reintroduce

Do not add memory extraction, lifecycle transitions, or any broker calls inside
`EventStore.append_event()` or any backend store's `append_event()`. If you
find yourself doing this, you are re-introducing the ADR-023 violation.

The convenience of implicit extraction is real. The architectural cost is higher.

---

*See also: ADR-023, T1 (Replay Equivalence), T2 (Projection Purity)*
