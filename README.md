# RationaleVault (v1.3.0) — Event-Sourced Cognitive Memory & Context Optimization Layer for AI Agents

[![GitHub](https://img.shields.io/badge/GitHub-NeutronZero%2FRationaleVault-181717?style=flat&logo=github)](https://github.com/NeutronZero/RationaleVault)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-1771%20passing-brightgreen)](https://github.com/NeutronZero/RationaleVault)
[![Version](https://img.shields.io/badge/Version-v1.3.0-blue)](https://github.com/NeutronZero/RationaleVault/releases/tag/v1.3.0)

**Event-sourced cognitive continuity, multi-agent context compression, and shared memory infrastructure for AI workflows.**

- Event-sourced cognitive memory
- Deterministic projection architecture
- Unified retrieval orchestration
- Multi-agent context compilation
- Local-first SQLite runtime
- MCP + CLI integration

RationaleVault enables autonomous LLM agents — Claude, ChatGPT, Cursor, Copilot, and custom Model Context Protocol (MCP) clients — to resume work on complex codebases with full context continuity, within seconds, eliminating manual summarization and context drift.

---

## Why RationaleVault Exists

LLM agents lose context. As projects evolve over weeks or months, they accumulate decisions, lessons, failures, architectural constraints, and rationale. Standard RAG tools and vector databases fail to preserve these because they lack structural temporal order, resulting in context drift, memory duplication, and decision degradation.

RationaleVault provides an event-sourced cognitive continuity layer. By treating events as the immutable source of truth and compiling memory, knowledge, and graphs as deterministic projections, RationaleVault ensures agents can reconstruct state and continue work with zero cognitive loss.

Now in `v1.3.0`, RationaleVault provides unified retrieval orchestration, provider-backed candidate generation, retrieval telemetry with CLI and MCP dashboards, and a decoupled MCP boundary — all built on a stable provider capability API.

## What's New in v1.3.0

- **Unified retrieval orchestration** with 9 retrieval profiles flowing through the pipeline
- **Provider capability API** (`search_records`, `get_by_ids`, `count`) with SQL-optimized implementations
- **Provider-backed candidate generation** replacing full-corpus scans
- **Batched citation lookups** for memory and knowledge
- **Retrieval telemetry** with CLI and MCP dashboards (percentiles, profile distribution, stage timings)
- **MCP boundary cleanup** through shared organization service

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
Event Ledger (Immutable Ledger Store)
      │
      ▼
SchemaPolicy (Per-Event-Type Migration Authority)
      │
      ▼
Replay Pipeline (Policy-Driven Resolver + Upcaster Registry)
      │
      ▼
Canonical Events (Schema-Normalized, Version-Agnostic)
      │
      ▼
Deterministic Projection Layer
  ├── Base Projections (Memory Projection)
  ├── Derived Projections (Knowledge Projection)
  └── Composite Projections (Context, Graph, Org Projections)
      │
      ▼
Cognitive Runtime
  ├── Retrieval Orchestrator
  ├── Recommendation Engine
  └── Skill Runtime
      │
      ▼
Delivery Layer (Agent Compiler, MCP Server, CLI, REST, SDK)
      │
      ▼
External Consumers (Claude, OpenCode, Codex, Cursor, CI/CD, Developers)
```

---

## SchemaPolicy Architecture

RationaleVault uses a policy-driven approach to schema evolution. Each event type has its own independent migration path, governed by `SchemaPolicy` — the sole authority for canonical version selection.

```text
GovernanceState
      │
      ▼
SchemaPolicyFactory
      │
      ▼
SchemaPolicy (per event type)
      │
      ▼
ReplayResolver + UpcasterRegistry
      │
      ▼
Canonical Event (normalized to latest version)
```

**Key properties:**
- Reducers never inspect schema versions — they consume canonical payloads
- Migration graphs are isolated per event type — no cross-event-type dependencies
- Adding a new migrated event type requires only registration, not engine changes
- Replay is deterministic and idempotent across all event types

---

## Release Evolution

| Version | Theme |
|---------|-------|
| **v1.1** | Organizational intelligence, recommendation engines, performance optimizations |
| **v1.2** | SchemaPolicy — per-event-type schema evolution, production-validated governance |
| **v1.3** | Intelligent retrieval & observability — unified orchestration, provider capabilities, telemetry |

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
All 1771 tests will execute (1771 pass; 14 expected skips).

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
- **`rationalevault retrieval-dashboard`**: Display retrieval telemetry dashboard with latency percentiles, profile distribution, and stage timings.
- **`rationalevault mcp`**: Start the Model Context Protocol (MCP) server for native LLM agent tool integration.

---

## Design Principles
- **Ledger Invariance**: The immutable event sequence is the only authoritative source of truth.
- **Determinism**: Identical event streams project to identical memory, knowledge, and graph states.
- **Provenance Traceability**: Every context citation carries strict lineage back to the originating event IDs.
- **Zero-Dependency Core**: Standard configuration runs local-first on SQLite with zero external database setup.
- **Projection Composition**: Higher-level projections may depend only on immutable state or lower-level projections.
- **Evaluation-Driven Evolution**: Every new projection, engine, or retrieval strategy must introduce deterministic evaluation metrics and regression gates before becoming part of the architecture.
- **Observable Retrieval**: Retrieval behavior should be measurable through deterministic telemetry so that optimization decisions are based on evidence rather than intuition.
- **Projection Monotonicity**: A projection may consume only immutable state or lower-level projections. Projections must never depend on runtime outputs, delivery artifacts, or other execution results.

> [!IMPORTANT]
> **State flows downward; behavior flows upward.** Immutable events produce persistent state. Persistent state produces deterministic projections. Projections feed the Cognitive Runtime. The Cognitive Runtime produces outputs through the Delivery Layer. No runtime component may mutate projections or persistent state directly; every state transition must occur exclusively through appending new events to the Event Ledger.
>
> **Projection Dependency Rule:** Projection dependencies form a Directed Acyclic Graph (DAG). Every projection depends only on immutable state or lower-level projections. Cyclic projection dependencies are prohibited.

## Architecture Governance

```
README (orientation)
    ↓
architecture.md (structural overview)
    ↓
SchemaPolicy Design (policy-driven schema evolution)
    ↓
docs/adr/ (rationale behind decisions)
    ↓
roadmap.md (planned evolution)
```

| Document | Purpose |
|----------|---------|
| [architecture.md](docs/architecture.md) | Data-flow pipelines and projection hierarchy |
| [ADRs](docs/adr/) | Architecture Decision Records — why each choice was made |
| [Skill Runtime](docs/skill_runtime_architecture.md) | Epic C design specification (Decision→Skill→Execution) |
| [Freeze Levels](docs/freeze_levels.md) | L1/L2/L3 taxonomy and change-process requirements |
| [Roadmap](docs/roadmap.md) | Engineering commitments and research vision |
| [Philosophy](docs/philosophy.md) | Core design principles |

