# RationaleVault (v1.1.0)

**Event-sourced cognitive continuity and memory layer for multi-agent AI workflows.**

RationaleVault enables any AI agent — Claude, OpenCode, ChatGPT, Cursor, Copilot — to resume work on a project with full context continuity, within 30 seconds, without manual summarization.

---

## Why RationaleVault Exists

LLM agents lose context. As projects evolve over weeks or months, they accumulate decisions, lessons, failures, architectural constraints, and rationale. Standard RAG tools and vector databases fail to preserve these because they lack structural temporal order, resulting in context drift, memory duplication, and decision degradation.

RationaleVault provides an event-sourced cognitive continuity layer. By treating events as the immutable source of truth and compiling memory, knowledge, and graphs as deterministic projections, RationaleVault ensures agents can reconstruct state and continue work with zero cognitive loss.

Now in `v1.1.0`, RationaleVault expands from single-project memories to **cross-project organizational intelligence** and **proactive recommendation loops**, giving agents deep structural visibility across your entire development portfolio.

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
Cross-Project Projection (Multi-Repo Blending & Isolation)
      ↓
Organization Graph (IN_CLUSTER & TRANSFER Relationships)
      ↓
Organization Continuation (Cross-Project Activity Level)
      ↓
Recommendation Engine (Drift, Blocker, & Merge Logic)
      ↓
Context Construction (Profile Slot Allocation Blending)
      ↓
Context Evaluation (Completeness & Traceability)
      ↓
Agent Compilers & MCP Server (Prompt Serialization / Adapters)
      ↓
Continuity Validation (Handoff Integrity Verification)
```

---

## Quick Start

### 1. Install RationaleVault

Install the package directly from PyPI:
```bash
pip install rationalevault
```

Or for development / running from source:
```bash
pip install -e ".[dev]"
```

### 2. Initialize a Project

Initialize RationaleVault in your current project workspace:
```bash
rationalevault init
```
This bootstraps the local configuration and state tracking directory (`.rationalevault/`).

### 3. Verify Installation

Run the system diagnostics tool to verify that the databases, compiler registry, and projection chains are fully functional:
```bash
rationalevault doctor
```

### 4. Run the Unified Evaluation Suite

Execute the full evaluation pipeline, verifying all layers of the cognitive continuity loop (Memory, Knowledge, Context, Compilers, Continuity, Graph, and Examples):
```bash
rationalevault evaluate
```
This writes a machine-readable snapshot to `.rationalevault/reports/release_manifest.json` and a human-readable summary to `.rationalevault/reports/report.md`.

### 5. Run Tests
For developers running from source:
```bash
pytest
```
All 876 tests will execute (862 pass; 14 require a live PostgreSQL database and are skipped by default).

---

## CLI Reference

RationaleVault provides a unified command-line toolset for inspecting and managing the cognitive ledger and projections:

- **`rationalevault init`**: Initialize RationaleVault configs and adapters in the current directory.
- **`rationalevault doctor`**: Run active diagnostics checks on storage, thresholds, registry, and projection chains.
- **`rationalevault evaluate`**: Run the self-verifying exit-gate evaluation suite across all subsystems.
- **`rationalevault memory`**: Query and manage the memory layer.
- **`rationalevault knowledge`**: Inspect synthesized project invariants, rules, and architecture guidelines.
- **`rationalevault context`**: Compile queries into formatted context packages ready for agent consumption.
- **`rationalevault graph`**: Build, serialize, and check statistics on the derived knowledge projection.
- **`rationalevault organization`**: Multi-project graph topology, lineages, reachability, and cluster analysis.
- **`rationalevault recommendation`**: Generate proactive merge recommendations, blockers, and drift warnings.
- **`rationalevault mcp`**: Start the Model Context Protocol (MCP) server for native LLM agent tool integration.

---

## Design Principles
- **Ledger Invariance**: The immutable event sequence is the only authoritative source of truth.
- **Determinism**: Identical event streams project to identical memory, knowledge, and graph states.
- **Provenance Traceability**: Every context citation carries strict lineage back to the originating event IDs.
- **Zero-Dependency Core**: Standard configuration runs local-first on SQLite with zero external database setup.

