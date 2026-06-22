"""RationaleVault Knowledge Lineage — Provenance tracking for synthesized knowledge.

Every KnowledgeObject must be traceable back to source memories and source events.
This module provides the tools to build and verify those chains.
"""
from __future__ import annotations

from typing import Any, Optional

from rationalevault.knowledge.models import KnowledgeConfidence, KnowledgeObject, ProvenanceChain
from rationalevault.memory.factory import get_memory_provider


def build_provenance_chain(
    knowledge_id: str,
    source_memory_ids: list[str],
    synthesis_event_id: str = "",
) -> ProvenanceChain:
    """Build full provenance chain from memory IDs back to events.

    Args:
        knowledge_id: The ID of the knowledge object being created.
        source_memory_ids: List of memory IDs used in synthesis.
        synthesis_event_id: The event ID that triggered this synthesis.

    Returns:
        ProvenanceChain with full traceability.
    """
    provider = get_memory_provider()
    all_memories = {m.id: m for m in provider.get_all_records()}

    source_event_ids: list[str] = []
    total_confidence = 0.0
    count = 0

    for mid in source_memory_ids:
        mem = all_memories.get(mid)
        if mem:
            source_event_ids.extend(mem.source_event_ids)
            total_confidence += mem.confidence
            count += 1

    avg_confidence = total_confidence / count if count > 0 else 0.0

    confidence = KnowledgeConfidence(
        memory_count=count,
        source_event_count=len(set(source_event_ids)),
        contradiction_count=0,
        average_memory_confidence=avg_confidence,
    )

    return ProvenanceChain(
        knowledge_id=knowledge_id,
        source_memory_ids=source_memory_ids,
        source_event_ids=list(set(source_event_ids)),
        synthesis_event_id=synthesis_event_id,
        confidence=confidence,
        evidence_count=count,
    )


def verify_provenance(knowledge: KnowledgeObject) -> bool:
    """Verify that all source memories and events still exist.

    Args:
        knowledge: The knowledge object to verify.

    Returns:
        True if provenance is complete and valid.
    """
    # Check source memories exist
    provider = get_memory_provider()
    all_memory_ids = {m.id for m in provider.get_all_records()}

    for mid in knowledge.provenance.source_memory_ids:
        if mid not in all_memory_ids:
            return False

    # Note: Full event verification would require EventStore.get_event_by_id
    # which is not yet implemented. For now, we verify memories exist.
    return True


def get_memory_lineage(memory_id: str) -> list[dict[str, Any]]:
    """Get the lineage of a memory back to its source events.

    Args:
        memory_id: The memory ID to trace.

    Returns:
        List of event dicts representing the lineage chain.
    """
    provider = get_memory_provider()
    all_memories = {m.id: m for m in provider.get_all_records()}

    mem = all_memories.get(memory_id)
    if not mem:
        return []

    lineage = []
    for event_id in mem.source_event_ids:
        lineage.append({
            "memory_id": memory_id,
            "event_id": event_id,
            "memory_type": mem.memory_type.value,
            "source_type": mem.source_type,
        })

    return lineage


def compute_provenance_depth(knowledge: KnowledgeObject) -> int:
    """Compute the depth of the provenance chain.

    Args:
        knowledge: The knowledge object to measure.

    Returns:
        Number of layers in the provenance chain.
    """
    # Depth = unique source memories + unique source events
    return len(knowledge.provenance.source_memory_ids) + len(
        set(knowledge.provenance.source_event_ids)
    )
