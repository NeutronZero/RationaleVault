# Changelog

All notable changes to RationaleVault will be documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-06-22

### Added
- Renamed the entire project package namespace from `relay` to `rationalevault`.
- Created dual entrypoint and unified CLI binary `rationalevault` as the sole public command.
- Integrated examples directly into the package (`rationalevault.examples`) so they can be run from any CWD.

### Fixed
- Fixed CWD-sensitive asset loading in `rationalevault doctor` and `rationalevault evaluate` by utilizing `importlib.resources` instead of relative workspace paths. This allows running active diagnostics and evaluations on arbitrary directories after wheel installation.

---

## [1.0.0rc2] — 2026-06-22

### Changed
- Centralized package and schema version into `relay/__init__.py`.
- Formatted version as PEP 440-compliant `1.0.0rc2`.
- `rationalevault doctor` and `rationalevault evaluate` now both consume the central `__version__` and `SCHEMA_VERSION` constants.

---

## [1.0.0rc1] — 2026-06-22

### Sprint I8 — Release Hardening
- **Unified Evaluation Framework**: Single CLI entry point (`rationalevault evaluate`) that validates Memory, Knowledge, Context, Compilers, Continuity, Graph, and Examples in a single pass.
- **Active Diagnostics**: `rationalevault doctor` checks storage connection pools, evaluation assets, compiler adapters, and runs an end-to-end **Projection Chain Verification** (Event → Memory → Knowledge → Graph → Context → Compiler).
- **Release Manifest**: Outputs a machine-readable `release_manifest.json` snapshot at `.relay/reports/release_manifest.json` and a markdown summary at `.relay/reports/report.md`.
- **Installation Validator**: `relay.evaluation.validate_install` performs critical import verification across all pipeline stages.

### Sprint I7.5 — Knowledge Graph Projection
- **GraphProjection**: Deterministic, SHA-256-identified graph projection over all synthesized KnowledgeObjects and KnowledgeRelations.
- **Graph Evaluation**: Node coverage, edge coverage, referential integrity, determinism, orphan percentage, and connected component metrics with exit gate validation.
- **Graph Exports**: Mermaid, NetworkX, and GraphML serialization formats.
- **`rationalevault graph`** CLI subcommand: `build`, `stats`, `show`, `path`, `neighbors`.

### Sprint I7 — Multi-Agent Continuity Validation
- **Continuity Benchmarks**: Structured benchmark schema for agent handoff verification with artifact canonical/alias matching.
- **Corpus Builder**: Automated handoff corpus generation from conversation transcripts.
- **Continuity Evaluator**: Goal recall, decision recall, task recall, context gain, and rationale recall metrics.
- **`rationalevault context`** CLI subcommand with `--evaluate` mode for continuity analysis.

### Sprint I6–I6.5 — Agent Compiler Framework
- **Agent Compiler Registry**: Abstract compiler interface (`ContextCompilerBase`) and plugin registry for Claude, OpenCode, and Cursor adapters.
- **Claude Compiler**: Produces structured markdown with open questions, active tasks, decisions, and a resumption prompt.
- **OpenCode Compiler**: YAML-structured output optimized for structured agent contexts.
- **Cursor Compiler**: Context-aware output for IDE-integrated agents.
- **Compiler Evaluator**: Section coverage, keyword coverage, determinism, and compression ratio evaluation.

### Sprint I5–I5.5 — Context Construction
- **Context Compiler**: Query-intent-aware profile-based slot allocation blending events, memories, and knowledge into unified `ContextPackage`.
- **Query Profiles**: `context_construction`, `knowledge_review`, `decision_audit`, `default`, `diagnostic`.
- **Retrieval Profile Planner**: Slot budget allocation across source types for each profile.
- **Context Evaluation**: Completeness, source traceability, source balance, precision, redundancy, and timing budget metrics.
- **`rationalevault context`** CLI subcommand.

### Sprint I4–I4.5 — Knowledge Synthesis & Evaluation
- **Knowledge Synthesizer**: Derives structured `KnowledgeObject` instances (architecture principles, project invariants, implementation patterns, constraints, lessons learned) from memory records.
- **Knowledge Provider**: SQLite-backed persistent knowledge store.
- **Knowledge Evaluation**: Density, coverage, provenance percentage, contradiction detection, freshness, stability, and determinism metrics.
- **Knowledge Benchmark Schema**: Structured benchmark format for precision, semantic recall, identity recall, F1, and type coverage.
- **`rationalevault knowledge`** CLI subcommand.

### Sprint I3–I3.5 — Retrieval Intelligence
- **Ranked Retrieval**: Multi-factor retrieval scoring (priority, recency, reference count, confidence, lifecycle penalty).
- **Query Intent Analysis**: Automatic query profiling with intent-based source weighting.
- **Citation Builder**: Structured `MemoryCitation` with full retrieval path and reason codes.
- **Retrieval Benchmarks**: Precision@K, Recall@K, NDCG, and MRR metrics with benchmark-driven evaluation.
- **`rationalevault memory search`** CLI subcommand.

### Sprint I1–I2 — Memory Foundation & Intelligence
- **Event Ledger**: Append-only event store with SQLite and PostgreSQL backends. Events carry project ID, stream ID, type, payload, metadata, and parent linkage.
- **Event Schema**: Typed event system (`EventType` enum) covering all project lifecycle events.
- **Memory Extraction**: Deterministic `MemoryRecord` derivation from events with SHA-256-based IDs (idempotent re-extraction).
- **Memory Consolidation**: Duplicate cluster detection and consolidation candidate emission.
- **Memory Intelligence**: Reference counting, recency tracking, lifecycle status management.
- **Cognitive Head**: Append-only projection of agent task/decision/question state from the event stream.
- **`rationalevault init`**, **`rationalevault memory`**, **`rationalevault doctor`** CLI subcommands.

---

## [0.1.0] — 2026-06-01 (Sprint A + B + D)

### Initial Release
- Event-sourced event store with SQLite backend.
- Basic memory extraction and consolidation scaffold.
- CLI initialization (`rationalevault init`) with YAML protocol, skill, and handoff checklist templates.
- Platform adapter installation (`rationalevault install --platform claude|cursor|opencode|copilot`).
- Docker PostgreSQL environment configuration.
