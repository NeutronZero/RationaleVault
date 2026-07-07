# Projection Archetypes

Projections in RationaleVault are not monolithic. Depending on the complexity of the derived state and its downstream consumers, projections fall into three distinct archetypes.

## 1. Materialized State Projections
**Examples**: `GovernanceProjection`, `TimelineProjection`
These are the simplest and most common projections.
- **Functionality**: They listen to the event stream and construct a standard, deterministically updated Python dictionary or dataclass in memory.
- **Usage**: Typically used for direct querying via the CLI or MCP tools.
- **Determinism**: 100% pure deterministic reduction. Replaying the event stream will result in a bit-for-bit identical state tree.

## 2. Generative & Semantic Projections
**Examples**: `EmbeddingProjection`, `KnowledgeSynthesis`
These projections bridge the gap between deterministic event sequences and fuzzy semantic representation.
- **Functionality**: They take raw events (e.g., text blocks, decisions) and process them through local models (like `sentence-transformers`) to produce vector embeddings or synthesized semantic summaries.
- **Usage**: Used to populate FAISS indices or semantic vector stores for hybrid retrieval.
- **Determinism**: Quasi-deterministic. The resulting floating-point vectors may vary slightly across different hardware architectures or dependency versions, making bit-for-bit replay equivalence impossible. As a result, these projections rely heavily on versioned invalidation.

## 3. Distributed/Graph Projections
**Examples**: `CognitiveHead`, `ProjectRegistry`
These projections manage complex relationships across massive, interconnected event domains.
- **Functionality**: The `CognitiveHead` builds a directed acyclic graph (DAG) of beliefs, decisions, and evidence. The reductions involve propagation algorithms.
- **Usage**: They power the core intelligence and reasoning continuity of the system.
- **Determinism**: Structurally deterministic, but their execution footprint is extremely heavy. They require sophisticated `SnapshotPolicy` mechanics to freeze sub-graphs to disk periodically to prevent massive memory overhead.
