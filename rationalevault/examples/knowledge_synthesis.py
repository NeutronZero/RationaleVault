"""RationaleVault built-in example: Knowledge Synthesis pipeline (Memory -> Knowledge -> Graph).

Bundled inside the rationalevault package for CWD-independent execution.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeConfidence,
    ProvenanceChain,
)
from rationalevault.knowledge.relations import detect_relations
from rationalevault.knowledge.graph import GraphProjection
from rationalevault.knowledge.store import SQLiteKnowledgeProvider


def main() -> None:
    print("--- Running RationaleVault Example: Knowledge Synthesis ---")

    # 1. Setup temp database
    temp_dir = Path(tempfile.gettempdir())
    db_path = temp_dir / f"rv_example_knowledge_{uuid.uuid4().hex[:8]}.db"

    print(f"Initializing temporary Knowledge Store at: {db_path}")
    k_prov = SQLiteKnowledgeProvider(db_path=db_path)

    # 2. Setup mock knowledge objects
    conf = KnowledgeConfidence(1, 1, 0, 1.0)
    prov = ProvenanceChain("k1", ["m1"], ["e1"], "s1", conf, 1)

    k1 = KnowledgeObject(
        id="k1",
        version=1,
        title="Architecture Principle: Event Sourcing",
        content="All state changes in RationaleVault must be projected from an immutable event ledger.",
        knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=conf,
        importance="critical",
        provenance=prov,
    )

    k2 = KnowledgeObject(
        id="k2",
        version=1,
        title="Project Invariant: State is Derived",
        content="State in the cognitive layers is always derived from events, never stored directly.",
        knowledge_type=KnowledgeType.PROJECT_INVARIANT,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=conf,
        importance="critical",
        provenance=prov,
    )

    k_prov.add_knowledge(k1)
    k_prov.add_knowledge(k2)
    knowledge_list = k_prov.get_all_knowledge()

    # 3. Detect relations
    print("Detecting semantic relationships...")
    relations = detect_relations(knowledge_list)
    print(f"Detected {len(relations)} relationships.")

    # 4. Build graph projection
    print("Projecting into Knowledge Graph...")
    projection = GraphProjection.build(knowledge_list, relations)
    print(f"Graph ID: {projection.graph_id}")
    print(f"Nodes:    {projection.node_count}")
    print(f"Edges:    {projection.edge_count}")

    # 5. Export to Mermaid
    print("\nMermaid Export:")
    print("-" * 40)
    print(projection.export_mermaid())
    print("-" * 40)

    # Clean up
    import gc
    gc.collect()
    try:
        if db_path.exists():
            os.remove(db_path)
    except Exception:
        pass
    print("Example executed successfully!\n")


if __name__ == "__main__":
    main()
