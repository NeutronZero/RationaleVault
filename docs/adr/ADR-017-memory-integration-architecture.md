# ADR-017: Memory Integration Architecture

**Status**: Accepted
**Date**: 2026-06-26
**Deciders**: RationaleVault team
**Technical Story**: How should the Agent Runtime access the graph-backed memory substrate?

---

## Context

RationaleVault's memory layer is its core differentiator. It provides:
- Event-driven memory extraction
- BM25 + semantic retrieval with RRF fusion
- Knowledge synthesis (invariants, principles, lessons, patterns)
- Lifecycle management (MTRANS/MREP promotion pipeline)
- Provenance chains (events → memories → knowledge)

However, this memory substrate was disconnected from the Agent Runtime. Agents could only access memory through raw MCP tool calls that bypassed the runtime entirely. This meant:
1. No session-aware memory context
2. No capability-gated memory access
3. No standardized memory query/result contracts
4. No deduplication at the write boundary

## Decision

Introduce a **Memory Integration layer** that bridges the Agent Runtime with the memory substrate.

### Architecture

```
Agent Runtime
    ↕ AgentSession
Memory Integration (v2.6)
    ↕ MemoryBroker + MemoryContext
Memory Layer
    ↕ MemoryProvider + Retrieval
Knowledge Layer
    ↕ KnowledgeProvider
Event Ledger
```

### Key Design Decisions

**1. MemoryQuery as the universal read contract**

Every memory access goes through a `MemoryQuery`:
- `SEARCH` — keyword/semantic search
- `RETRIEVE` — direct ID lookup
- `CONTEXT` — blended context compilation
- `CONTINUATION` — where I left off
- `LINEAGE` — provenance chain traversal

This replaces ad-hoc retrieval calls with a typed, filterable contract.

**2. MemoryResult with provenance**

Every result carries:
- Score (from signal fusion ranking)
- Source event IDs (provenance chain)
- Source memory IDs (deduplication chain)
- Reasons (explainability)
- Retrieval path (audit trail)

This makes memory results auditable and explainable.

**3. MemoryContext as a snapshot**

The `MemoryContext` is a point-in-time snapshot, not a live connection. This enables:
- Session continuity (cache and reuse)
- Deterministic replay (same context = same results)
- Audit trails (context hash for verification)

**4. MemoryBroker as the orchestrator**

The `MemoryBroker` translates between runtime contracts and memory infrastructure:
- Maps `MemoryQueryType` → `RetrievalProfile`
- Maps `MemoryRecordType` ↔ `MemoryType`
- Handles deduplication on writes
- Caches contexts for session continuity

**5. Deduplication at the write boundary**

`MemoryWriteRequest` → `MemoryWriteResult` includes a `deduplicated` flag. If a memory with the same deterministic ID already exists, the write succeeds but is marked as deduplicated. This prevents duplicate memories without requiring the agent to check first.

## Consequences

### Positive
- Agents access memory through standardized, typed contracts
- Memory results carry full provenance for auditability
- Session continuity through context caching
- Deduplication prevents memory pollution
- Clean separation between runtime contracts and memory internals

### Negative
- One more abstraction layer (minimal overhead)
- Memory Broker must stay in sync with memory layer changes

## Alternatives Considered

### 1. Direct memory layer access from agents
**Rejected**: Breaks encapsulation, no capability checks, no standardized contracts.

### 2. Extend MCP tools to include memory
**Rejected**: MCP tools are presentation layer; memory integration is runtime layer.

### 3. Event-driven memory updates only
**Rejected**: Agents need synchronous read access for real-time queries.

## Relationships

- Depends on: Memory layer (existing), Agent Runtime (v2.2)
- Extends: MCP Server v2 (v2.5) — tools can use MemoryBroker
- Frozen: v2.6 (Memory Integration Freeze)

---

*ADR-017 — Accepted 2026-06-26*
