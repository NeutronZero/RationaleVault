# RationaleVault Context Assembly Planner

## Status: DEFERRED to Sprint D

The Context Assembly Planner (Phase R4) is not built in V1.

It will be implemented only if Sprint C failures show that the full Cognitive Head is too large for agent context windows, or that targeted retrieval would significantly improve handoff quality.

---

## What It Will Do

The Context Planner classifies incoming queries and assembles targeted context:

```python
intent = classify_intent(query)
# → STATUS_CHECK | NEXT_STEPS | ARCHITECTURE | DECISION | QUESTION | HISTORY

context = assemble_context(intent, head, knowledge)
# → Targeted subset, not the full head
```

### Intent → Retrieval Mapping

| Intent | Primary Source |
|--------|----------------|
| `STATUS_CHECK` | Cognitive Head (tasks, blockers) |
| `NEXT_STEPS` | Open Questions + Active Tasks |
| `ARCHITECTURE` | Accepted Decisions + Facts |
| `DECISION` | Decision history + Supersessions |
| `QUESTION` | Open Questions + Blockers |
| `HISTORY` | Event replay slice |

### Context Budget Manager

When the context block exceeds token budget:

```
Rank by:
  1. Importance (priority field)
  2. Confidence (fact confidence level)
  3. Recency (event_sequence)
  4. Relevance (to current intent)
```

## Lessons from Graph-RAG

The RTOS-Graph-RAG platform's retrieval system evolved from Sprint 7 through Sprint 23 by adding targeted retrieval only in response to observed accuracy failures. RationaleVault should follow the same pattern.

V1's full-head compilation is correct and sufficient until:
- Token budget is exceeded (context block > 8K tokens)
- Agents demonstrate they're ignoring parts of the context
- Specific query types show significantly worse recall

## When to Build This

Build the Context Planner when Sprint C shows:
- Context blocks exceed the target agent's effective context window
- Agents show lower recall on specific query types (architecture vs. status)
- Full-head compilation is too slow even with snapshots
