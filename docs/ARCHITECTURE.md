# Relay Architectural Architecture

This document details the data transitions, pipelines, and projections that drive Relay's cognitive memory framework.

---

## Complete Evolutionary Flow

Relay tracks project status by processing data through a sequence of projections:

```text
Event Stream
  ↓  (Memory Extraction & Deduplication)
Memory Store
  ↓  (Knowledge Synthesis & Contradiction Checking)
Knowledge Store
  ↓  (Semantic Relations & Topological Projection)
Knowledge Graph
  ↓  (Profile Blending & Slot Allocation)
Context Package
  ↓  (Prompt Formatting & Adapter Registries)
Agent Compiler Output
```

---

## Layer-by-Layer Projections

### 1. Events → Memories
Events are captured in the immutable ledger. When an event is appended, memory extraction rules parse it, check for duplicates, and record corresponding memory records.

```mermaid
graph TD
    A[Event Store Ledger] -->|Ingest EventRecord| B[Memory Extractor]
    B -->|Check Duplicates| C{Already Exists?}
    C -->|No| D[Create MemoryRecord]
    C -->|Yes| E[Increment Reference Count]
    D -->|Write| F[Memory Store]
    E -->|Update| F
```

### 2. Memories → Knowledge
Memory records are synthesized into high-level, declarative knowledge objects (project invariants, architectural decisions) while analyzing for contradictions.

```mermaid
graph TD
    A[Memory Store] -->|Aggregate Records| B[Knowledge Synthesizer]
    B -->|Scan for Conflicts| C{Contradictions Detected?}
    C -->|Yes| D[Emit Contradiction Event]
    C -->|No| E[Create/Update KnowledgeObject]
    E -->|Commit| F[Knowledge Store]
```

### 3. Knowledge → Graph
Knowledge objects and detected semantic relationships are projected into a topological knowledge graph projection.

```mermaid
graph TD
    A[Knowledge Store] -->|Load Objects| B[Relations Detector]
    B -->|Detect Domain/Tag overlap| C[Build KnowledgeRelations]
    A -->|Node Data| D[Graph Projection Builder]
    C -->|Edge Data| D
    D -->|Hash sorted nodes/edges| E[Deterministic Graph ID]
```

### 4. Graph → Context
Using the query keywords and the target profile (e.g. `DECISION_LOOKUP`), Relay determines source weights and retrieves items into slots.

```mermaid
graph TD
    A[Query + Profile] -->|Analyze Intent| B[Slot Allocator]
    B -->|Retrieve Events| C[Context Blending Engine]
    B -->|Retrieve Memories| C
    B -->|Retrieve Knowledge| C
    C -->|Sort by Relevance Score| D[Unified ContextPackage]
```

### 5. Context → Compiler → Agent
The unified context package is passed to the compiler registry where adapter-specific formatting prepares the prompt context block for a target LLM.

```mermaid
graph TD
    A[ContextPackage] -->|Registry Lookup| B[Agent Compiler Adapter]
    B -->|Claude Adapter| C[Format Markdown Context Block]
    B -->|Cursor Adapter| D[Format XML Context Block]
    C -->|Pass Prompt| E[Target Agent Ingestion]
    D -->|Pass Prompt| E
```
