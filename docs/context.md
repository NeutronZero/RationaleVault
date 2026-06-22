# Relay Context Construction

Relay compiles a unified context package from multiple sources.

---

## Blending Weights Matrix
Using the detected `RetrievalProfile`, Relay maps source allocation ratios:

| Profile | Events Ratio | Memories Ratio | Knowledge Ratio |
|---|---|---|---|
| `KNOWLEDGE_REVIEW` | 10% | 20% | 70% |
| `DECISION_LOOKUP` | 25% | 50% | 25% |
| `FAILURE_ANALYSIS` | 30% | 50% | 20% |
| `GENERAL_SEARCH` | 20% | 45% | 35% |

## Assembly
1. Extract query keywords and detect intent profile.
2. Retrieve candidates from Memory, Knowledge, and Event streams.
3. Allocate slots and merge items into a sorted, ranked `ContextPackage`.
