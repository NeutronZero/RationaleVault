# Relay Philosophy

Relay is built on a single, fundamental insight: **AI agents lose context, but multi-agent software engineering requires absolute cognitive continuity.**

When human engineers hand off projects, they write summaries, design docs, and commit messages. When AI agents hand off projects, they suffer from context compression, memory degradation, and knowledge drift. Relay solves this by providing a deterministic, event-sourced cognitive memory ledger.

---

## Core Pillars

### 1. Events as the Sole Source of Truth
In Relay, state is never primary. Every decision, task status, architectural principle, and resolved question is a projection compiled from an immutable event ledger.
- If you want to know *why* a decision was made, you replay the ledger.
- If a decision changes, a new event is appended. Historical context is never overwritten or mutated.

### 2. Projections over Databases
Relay does not maintain a runtime graph database, vector database, or key-value store as the source of truth. Memories, knowledge objects, and graph structures are transient projections derived from events. This guarantees:
- **Total Determinism**: Replaying the same ledger always produces the exact same knowledge graph and context package.
- **Traceability**: Every synthesized fact or citation is fully traceable to its source events.

### 3. Separation of Context from Orchestration
Relay is not an agent framework. It does not dictate how agents reason, plan, or loop. It resides purely at the cognitive infrastructure level, providing compiled context blocks to agents and ingesting events when they complete a turn.

---

## What Relay Is Not

To prevent conceptual drift, contributors must respect what Relay is not:
- **Not a Vector Database**: We do not perform semantic searches over raw embeddings. Context is compiled using query intent analyzer profiles and slot-based blending.
- **Not a Graph Database**: We do not maintain a live Neo4j/Arango instance. The graph is projected on-the-fly for structural navigation.
- **Not a Workflow Engine**: Relay does not run pipelines or manage agents.
- **Not an Agent Framework**: Relay works with Claude, ChatGPT, Cursor, and any other LLM by serializing context via agent-specific compilers.
