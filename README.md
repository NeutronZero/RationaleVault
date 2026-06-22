# RationaleVault (v1.0.0)

**Event-sourced cognitive continuity and memory layer for multi-agent AI workflows.**

RationaleVault enables any AI agent — Claude, OpenCode, ChatGPT, Cursor, Copilot — to resume work on a project with full context continuity, within 30 seconds, without manual summarization.

---

## Why RationaleVault Exists

LLM agents lose context. As projects evolve over weeks or months, they accumulate decisions, lessons, failures, architectural constraints, and rationale. Standard RAG tools and vector databases fail to preserve these because they lack structural temporal order, resulting in context drift, memory duplication, and decision degradation.

RationaleVault provides an event-sourced cognitive continuity layer. By treating events as the immutable source of truth and compiling memory, knowledge, and graphs as deterministic projections, RationaleVault ensures agents can reconstruct state and continue work with zero cognitive loss.

## What RationaleVault Is Not

To understand RationaleVault, it is helpful to clarify what it is not:
- **Not a vector database**: RationaleVault uses structured keyword, domain, and profile-based slot allocation for deterministic context compilation.
- **Not a graph database**: The knowledge graph in RationaleVault is a derived view (a projection), not a storage database.
- **Not a workflow engine**: RationaleVault does not execute agent loops or handle tasks; it provides cognitive memory infrastructure.
- **Not an agent framework**: RationaleVault is agent-agnostic and interfaces via standardized compiler adapters.
- **Not a memory database**: RationaleVault is event-sourced; the immutable event ledger is the sole source of truth.

---

## Architecture Flow

Every layer of RationaleVault has an implementation, evaluation metrics, and validation exit gates.

```text
Events (Ledger)
      ↓
Memory Extraction (Provenance / Deduplication)
      ↓
Memory Intelligence (Reference Counts / Recency)
      ↓
Retrieval Intelligence (Ranking & Keywords)
      ↓
Knowledge Synthesis (Synthesized Facts & Contradictions)
      ↓
Knowledge Evaluation (Density & Precision Gates)
      ↓
Knowledge Graph Projection (Nodes & Edge Integrity)
      ↓
Context Construction (Profile Slot Allocation Blending)
      ↓
Context Evaluation (Completeness & Traceability)
      ↓
Agent Compilers (Prompt Serialization / Adapters)
      ↓
Continuity Validation (Handoff Integrity Verification)
```

---

## Quick Start

### 1. Install RationaleVault

Install RationaleVault in editable developer mode:
```bash
pip install -e ".[dev]"
```

### 2. Verify Installation

Run the system diagnostics tool to verify that the environment, active databases, registry, and projection chains are fully functional:
```bash
rationalevault doctor
```

### 3. Run the Unified Evaluation Suite

Execute the full evaluation pipeline, checking all exit gates (Memory, Knowledge, Context, Compilers, Continuity, Graph, and Examples):
```bash
rationalevault evaluate
```

This generates a PEP 440-compliant release manifest at `.rationalevault/reports/release_manifest.json` and a markdown summary at `.rationalevault/reports/report.md`.

### 4. Run tests
```bash
pytest
```
All 283 tests will run (269 pass; 14 are skipped as they require a live PostgreSQL database connection).

---

## Design Principles
- **Ledger Invariance**: `event_sequence` is the only authoritative ordering key.
- **Determinism**: Same events always project to the identical memory, knowledge, and graph states.
- **Provenance Traceability**: Every context citation must trace back to original event ledger records.
- **Zero-Dependency Core**: Standard configuration runs local-first on SQLite with zero external database setup.
