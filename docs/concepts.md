# RationaleVault Concepts

RationaleVault relies on a few simple, powerful concepts.

---

## 1. Cognitive Continuity
Cognitive continuity is the measurement of context preservation during handoffs. If Agent A works on a task and hands it off to Agent B, Agent B should be able to resume with minimum information loss, avoiding repetitive queries or research steps.

## 2. Event Sourcing
Traditional memory systems update databases directly (destructive updates). RationaleVault records everything as an immutable stream of events (e.g., `PROJECT_GOAL_SET`, `DECISION_ACCEPTED`, `TASK_COMPLETED`). State is never modified; it is replayed.

## 3. Cognitive Projections
Projections are read-only views computed by folding events in sequence. If we need a list of active tasks, we fold the events to build a "Cognitive Head". If we need semantic relationships, we project a "Knowledge Graph". This ensures state can always be re-derived.
