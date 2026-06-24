# RationaleVault Roadmap

This roadmap outlines current architectural freeze zones and plans for upcoming releases.

---

## v1.0.0 (Release Candidate)
- **Immutable Ledger**: Append-only event store supporting SQLite and PostgreSQL backends.
- **Cognitive Head**: Real-time project tracking (goals, decisions, rationales, tasks, questions).
- **Projections**: Independent memory deduplication, knowledge synthesis, and graph projection pipelines.
- **Context Compilation**: Slot-blended context packages based on query profiles.
- **Unified Evaluation**: Authorities system checks and diagnostics via CLI (`rationalevault doctor`, `rationalevault evaluate`).

## v1.1.0 (Organizational Release)
- **Cross-Project Sharing**: Allow agents to reference patterns, architecture rules, and lessons learned across separate repository ledgers using the new `OrganizationState` projection.
- **Organization Graph**: Derived cross-project relations (IN_CLUSTER and TRANSFERRED_TO) mapped topolocigally.
- **Recommendation Engine**: Proactive recommendation generation checking conflicts, duplicates, and project drift.
- **MCP Server Support**: Standardized tool interface via Model Context Protocol.
- **Hardening & Determinism**: Standardized `reference_time` run environment, optimized Jaccard Union complexity, and iterative DFS graph safety.

---

## v1.x (Stability & Presentation Track)
- **Packaging Refinements**: Optimize installation distribution on PyPI.
- **Documentation & Localization**: Maintain concise conceptual articles and guide enhancements.
- **Performance Adjustments**: Optimize database locks and connection speeds for high-frequency workflows.

---

## v2.0.0 (Research Track)
- **Graph-RAG Integration**: Project hybrid semantic indices that combine vector searches with topological navigation.
- **User-owned Memory Profiles**: Support personalized memory scopes (e.g. tracking specific engineer workflows vs agent loops).
- **Semantic Reasoners**: Advanced contradiction resolver rules.
