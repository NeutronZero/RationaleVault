# Changelog

All notable changes to RationaleVault will be documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.0] — 2026-07-07

### Added
- **GovernanceProjection** (Phase E): Fifth archetype validation — Evaluation projection.
  - `GovernanceSeverity` and `GovernanceAction` enums.
  - `GovernanceCondition` and `GovernanceRule` domain models.
  - `RuleEvaluation` and `GovernanceWarning` evaluation outcomes.
  - `GovernanceState` — stored policy rules list.
  - `GovernanceEvidenceProvider` protocol and `DefaultEvidenceProvider` implementing composition over recommendation facts.
  - `GovernanceProjection` — pure reducer processing governance rule events.
  - `GovernanceRuntime` — evaluates policies using collected evidence (never mutates).
  - CLI: `rv governance show --limit 50 --severity critical --action block`.
  - MCP tool: `get_warnings(limit, severity, action)`.
  - Conformance Suite: all 7 Projection Laws verified without platform changes.
  - Benchmarks: rule evaluation performance, average evidence size, warning counts.

### Changed
- ADR-027 Validation: GovernanceProjection verified — fifth projection on the platform.
  - Five archetypes validated: Aggregation, Materialization, Normalization, Derivation, Evaluation.
- `CHANGELOG.md`: Phase E entry.

---

## [1.7.0] — 2026-07-07

### Added
- **RecommendationProjection** (Phase D): Fourth archetype validation — analytical/derived projection.
  - `RecommendationCategory` — enum for five recommendation categories.
  - `Recommendation` — deterministic analytical fact with rule_id and rationale.
  - `RecommendationState` — sorted list of recommendations with sequence tracking.
  - `RecommendationRule` — abstract base for deterministic rule generation.
  - `RecommendationRuleRegistry` — deterministic rule ordering by rule_id.
  - 5 concrete rules: KnowledgeGap, TaskFollowUp, DecisionReview, QuestionResolution, KnowledgeDeletionRisk.
  - `RecommendationProjection` — pure reducer, serialize/deserialize, health lifecycle.
  - `RecommendationRuntime` — query/filter/rank layer (never mutates state).
  - CLI: `rv recommendation show --limit 10 --for "task_id" --category risk`.
  - MCP tool: `get_recommendations(limit, entity, category)`.
  - Conformance Suite: all 7 Projection Laws verified without platform changes.
  - Benchmarks: generation time, search latency, scalability, density, rule hit rate.

### Changed
- ADR-027 Validation: RecommendationProjection verified — fourth projection on the platform.
  - Four archetypes validated: state-reducing, searchable, narrative, analytical.
- `CHANGELOG.md`: Phase D entry.

---

## [1.6.0] — 2026-07-07

### Added
- **TimelineProjection** (Phase C): Third archetype validation — narrative projection.
  - `TimelineCategory` — enum for seven narrative categories.
  - `TimelineEntry` — normalized historical record (stable domain model).
  - `TimelineState` — append-only list of entries with sequence tracking.
  - `normalize_event()` — declarative mapping from events to entries.
  - `render_summary()` — separate presentation layer (swappable).
  - `TimelineProjection` — pure reducer, serialize/deserialize, health lifecycle.
  - CLI: `rv timeline show --limit 50 --category decision --format table`.
  - MCP tool: `get_timeline(limit, category)`.
  - Conformance Suite: all 7 Projection Laws verified without platform changes.
  - Benchmarks: snapshot growth, append throughput, replay amplification, entry density.

### Changed
- ADR-027 Validation: TimelineProjection verified — third projection on the platform.
  - Three archetypes validated: state-reducing (CognitiveHead), searchable (Embedding), narrative (Timeline).
- `CHANGELOG.md`: Phase C entry.

---

## [1.5.0] — 2026-07-07

### Added
- **EmbeddingProjection** (Phase B): First new projection on the ADR-027 Projection Platform.
  - `EmbeddingState` — canonical text and provenance metadata for knowledge nodes.
  - `CanonicalKnowledgeRenderer` — deterministic, order-stable rendering.
  - `EmbeddingProjection` — pure reducer consuming knowledge lifecycle events.
  - `EmbeddingProvider` protocol + `SentenceTransformerProvider`.
  - `EmbeddingBuilder` — incremental vector generation with content_hash caching.
  - `FAISSAdapter` — FAISS-backed RuntimeAdapter for semantic search.
  - CLI: `rv embedding search "query" --k 5`.
  - MCP tool: `search_embeddings(query, k)`.
  - Conformance Suite: all 7 Projection Laws verified without platform changes.
- **Knowledge Lifecycle Events**: `KNOWLEDGE_CREATED`, `KNOWLEDGE_UPDATED`, `KNOWLEDGE_DELETED`.
  - First-class knowledge lifecycle events (not embedding-specific).
  - Backward compatible with existing `KNOWLEDGE_SYNTHESIZED` and `KNOWLEDGE_SUPERSEDED`.
  - Applied in ledger order; last applicable event determines final state.
- **Embedding Benchmarks**: cold build, delta rebuild, snapshot roundtrip, search latency.

### Changed
- ADR-027 Validation: EmbeddingProjection verified — second projection on the platform.
- `pyproject.toml`: optional `[embed]` dependencies (sentence-transformers, faiss-cpu).

---

## [1.4.0] — 2026-07-07

### Added
- **SnapshotStore V2**: Deterministic snapshot-assisted replay (ADR-026).
  - `SnapshotManager` lifecycle — load, validate, save, refresh, delete.
  - `ReplayEngine` abstraction — owns all replay strategy (full, delta, fast path).
  - `ReplayReport` telemetry — replay mode, event counts, timing, snapshot status.
  - `EventCountPolicy` — configurable threshold (default: 100 new events).
  - `NullSnapshotManager` — Null Object pattern; compiler always has a SnapshotManager.
  - `with_hash()` returns immutable payload (value objects).
  - `CognitiveHeadSnapshotPayload.from_cognitive_head()` accepts full reducer state for delta replay.
- **Replay Equivalence Tests**: 44 tests proving reducer invariants and replay correctness.
  - `TestReducerIncrementalInvariant` — `reduce(A+B) == reduce(B, initial_state=reduce(A))`.
  - `TestReplayEquivalence` — 20 random streams + hand-crafted + exhaustive split.
  - `TestCumulativeDrift` — 500-event stream replayed in chunks of 50.
  - `TestSnapshotDeterminism` — same events produce identical snapshot bytes.
- **PostgreSQL CI**: Full test suite validates backend parity.
- **Replay Equivalence CI**: Required status check on every PR.
- **Backend Parity CI**: Snapshot tests run on both SQLite and PostgreSQL.
- **Nightly Benchmarks**: Scheduled workflow with history tracking.
- **Benchmark History**: `benchmarks/history/` with daily JSON snapshots.
- **Pytest Markers**: `snapshot` and `replay_equivalence` for targeted test selection.

### Changed
- **Compiler**: Delegates replay to `ReplayEngine.build_projection()`.
- **Reducers**: Support optional `initial_state` for incremental replay.
- **Snapshot Payload**: `from_cognitive_head()` stores full reducer state (tasks, decisions, questions) for delta replay.
- **Benchmarks**: Prove 43–95% replay improvement depending on snapshot ratio.

### Performance

| Events | Snapshot % | Full (ms) | Delta (ms) | Improvement |
|--------|-----------|-----------|------------|-------------|
| 1,000  | 50%       | 1.61      | 0.84       | 48.1%       |
| 5,000  | 50%       | 8.57      | 4.85       | 43.4%       |
| 10,000 | 50%       | 22.12     | 8.94       | 59.6%       |
| 5,000  | 90%       | 9.05      | 1.07       | 88.1%       |
| 5,000  | 99%       | 8.56      | 0.37       | 95.7%       |
| 10,000 | 99%       | 17.53     | 0.84       | 95.2%       |

### Compatibility
- No public API breaking changes.
- Existing projects require no migration beyond applying database schema version 0003.

### Verification
- Full snapshot lifecycle tested on both SQLite and PostgreSQL.
- Replay equivalence verified via 44 invariant tests.
- 1,870 tests pass. Ruff clean.

---

## [1.3.1] — 2026-07-06

### Fixed
- **Silent Exception Swallow**: Memory extraction failures now emit a warning to stderr instead of failing silently, while preserving successful event append semantics.
- **Circular Import Risk**: Moved `EventStore` import inside `handle_lifecycle_transitions()` to eliminate latent circular import risk in `memory/lifecycle.py`.
- **MarkdownMemoryProvider Thread Safety**: Added `threading.Lock` around the read-modify-write cycle in `add_record()`. Thread-safe, not multi-process safe.
- **Reserved EventTypes Documentation**: Clarified that `FACT_RECORDED`, `RELATIONSHIP_CREATED`, and `RELATIONSHIP_SUPERSEDED` are reserved for future relation persistence.

---

## [1.3.0] — 2026-07-06

### Added
- **Retrieval Telemetry Subsystem**: In-memory ring buffer collector (`RetrievalMetricsCollector`) with percentile calculations (p50, p95, p99), profile distribution tracking, and stage timing averages.
- **CLI Retrieval Dashboard**: `rationalevault retrieval-dashboard` command displaying latency percentiles, provider metrics, profile distribution, and per-stage timing.
- **MCP Retrieval Dashboard**: `retrieval_dashboard` tool returning structured telemetry data.
- **Retrieval Orchestrator**: Unified intent classification via `RetrievalOrchestrator` with 9-profile mapping (`_INTENT_PROFILE_MAP`), replacing `analyze_query()` in production paths.
- **Provider Capability API**: `search_records()`, `get_by_ids()`, `count()` methods on `BaseMemoryProvider` with SQL-optimized implementations in `SQLiteMemoryProvider`.
- **Organization Service**: `rationalevault/organization/service.py` with `build_org_state_from_registry()` — shared domain logic for CLI and MCP.

### Changed
- **Candidate Generation**: Retrieval now uses `provider.search_records(limit=200)` instead of `get_all_records()` for better performance.
- **Citation Lookups**: Batched memory and knowledge lookups via `get_by_ids()` and `get_knowledge_by_ids()` in `_blend_citations`.
- **MCP Boundary**: All 5 `from rationalevault.cli.main` imports in `mcp/tools.py` replaced with `from rationalevault.organization.service`.
- **Intent Classification**: `compile_context()` and `retrieve_ranked_citations()` now use `RetrievalOrchestrator` as single entry point. Caller-provided plan takes precedence.
- **Query Analyzer**: Fixed duplicate "exist" stopword.
- **Context Evaluator**: Fixed forward reference in `ContextEvalResult.from_dict`.
- **Version**: Bumped from `1.2.1` to `1.3.0`.

### Removed
- **Dead Code**: 12 source files (6 knowledge/, 6 memory/) and 7 test files with zero external imports.
- **Unused Imports**: ~200 unused imports removed via `ruff check --select F401 --fix`.

### Fixed
- **Benchmark Stability**: Warm-up iterations increased to 5, median of 20 runs, 50× budget. Test registry locking speedup via `time.time` patching.
- **Flaky Test**: `test_registry_locking` reduced from 5s to 0.5s.

---

## [1.2.1] — 2026-07-01

### Added
- **BaseProjection Alignment**: All 9 projection classes now inherit from `BaseProjection` with declared `ClassVar` metadata (`projection_kind`, `build_version`, `dependencies`). Projections: `SessionProjection`, `ContinuationProjection`, `KnowledgeProjection`, `GraphProjection`, `CrossProjectProjection`, `OrganizationProjection`, `OrganizationGraphProjection`, `OrganizationActivityProjection`, `OrganizationContinuationProjection`.
- **Epistemic Status**: Added `epistemic_status` attribute to `KnowledgeObject` with full serialization/deserialization support. States: `PROPOSED`, `VALIDATED`, `INVARIANT`, `CONFLICTED`, `TOMBSTONED`.
- **Canonical Event Registration**: Added `GOVERNANCE_DECISION_RECORDED`, `SKILL_EXECUTED`, `KNOWLEDGE_PROMOTION_CANDIDATE`, `KNOWLEDGE_PROMOTION_ASSESSED`, `KNOWLEDGE_PROMOTION_GATED`, `KNOWLEDGE_PROMOTION_APPROVED`, `KNOWLEDGE_PROMOTION_REJECTED` to `EventType` enum.
- **Governance Structures**: Added `GovernanceDomain`, `GovernanceAction` enums and `GovernanceRecord` frozen dataclass with `to_dict`/`from_dict` support.
- **EventRecord Schema Version**: Added `schema_version: int = 1` field to `EventRecord` dataclass, resolving a defect where `SchemaPolicy` and `ReplayResolver` referenced `event.schema_version` on a type that lacked it.

### Changed
- Version bumped from `1.2.0` to `1.2.1` in `pyproject.toml` and `__init__.py`.
- `OrganizationActivityState` and `OrganizationGraphState` now have `from_dict()` class methods for full serialization roundtrip support.

### Fixed
- Fixed mocked data type mismatch in `tests/unit/organization/test_graph_projection.py`.

---

## [1.2.0] — 2026-06-30

### Added
- **SchemaPolicy Architecture (F11–F16)**: Complete policy-driven schema evolution infrastructure.
  - `SchemaPolicy`: Immutable value object answering schema questions per-event-type.
  - `SchemaPolicyFactory`: Compiles policy from `GovernanceState`.
  - `ReplayResolver`: Pure policy executor with zero schema knowledge.
  - `UpcasterRegistry`: Pure data structure mapping event types to upcaster callables.
  - `ReplayContext`: Pure dataclass carrying `max_sequence` and `schema_policy`.
- **Production Schema Evolution**: Two independent production migrations validated.
  - `TASK_CREATED` v1→v2: Flat title/description to nested details structure.
  - `DECISION_PROPOSED` v1→v2: Enrichment with `context` and `category` fields.
- **Governance Integration**: Schema changes driven by `GovernanceState` projections.
- **Migration Specifications**: Formal contracts for each schema migration.
- **Integration Proof Suites**: 15 behavioral proofs across F15 and F16.
- **Architectural Guards**: AST-based enforcement of T14/T15 invariants.
- **Performance Baselines**: Relative regression budget testing for migration overhead.

### Changed
- `DecisionReducer`: Now consumes canonical `DECISION_PROPOSED` v2 schema (version-agnostic).
- `UpcasterRegistry.default()`: Pre-populated with both production upcasters.

### Frozen APIs
The following APIs are now stable and will be preserved except through documented deprecation:
- `SchemaPolicy`, `EventSchema`, `MigrationPath`, `MigrationStep`
- `SchemaPolicyFactory`
- `ReplayResolver`
- `ReplayPipeline`
- `ReplayContext`, `InterpretiveContext`
- `ReplayRequest`
- `GovernanceProjection`, `GovernanceState`

### Known Limitations
- `compile_at_sequence()` historical governance not yet production-complete (planned F17).
- `Replay Auditor` designed but not yet active (planned F18).
- Only two production event migrations currently exist.
- `COUNTERFACTUAL` replay mode reserved and not implemented.

---

## [1.1.0] — 2026-06-24

### Added
- **Organizational Intelligence (I11–I14)**: Introduced cross-project organization projection, graph topology, activity stream analysis, and continuation models.
- **Recommendation Engine (I15)**: Added automated recommendations for duplicate cluster consolidation, drift warnings, and checklist additions.
- **Audit Remediation**: Secured project isolation in storage layers, corrected compiler adapter signature mismatches, and filled provenance chain gaps.
- **Determinism Contract**: Standardized all projections to support deterministic `reference_time` runs using a centralized helper.
- **Performance Optimization**: Re-engineered Jaccard similarity union size arithmetic to reduce organization graph construction complexity from `O(C × S² × L)` to `O(L + C × S²)` with zero set allocations.
- **Graph Safety**: Replaced all recursive graph traversals with memory-safe, stack-based iterative DFS traversals (`dependency_chain()`, `all_paths()`, `_dfs_cycles()`) to prevent recursion limits on deep structures.
- **Retrieval Hardening**: Added module-level pre-compiled regex tokenization for triggers/intent classification, and made retrieval profiles and weight structures immutable using `MappingProxyType`.
- **Registry Concurrency Lock**: Added atomic directory write-locking (`os.mkdir` lock) to serialize registry modifications and prevent corruption under concurrent runs.

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
