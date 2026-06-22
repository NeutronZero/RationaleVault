"""Relay Knowledge Relations — Knowledge relationships and graph.

Detects SUPPORTS, CONTRADICTS, DERIVED_FROM, and RELATED_TO relations
between knowledge objects.
"""
from __future__ import annotations

from relay.knowledge.models import KnowledgeObject, KnowledgeRelation
from relay.memory.consolidation import jaccard_similarity


def detect_relations(knowledge: list[KnowledgeObject]) -> list[KnowledgeRelation]:
    """Detect relations between all knowledge objects.

    Relation types:
        - CONTRADICTS: Knowledge A conflicts with Knowledge B
        - SUPPORTS: Knowledge A reinforces Knowledge B
        - DERIVED_FROM: Knowledge A was synthesized from Knowledge B
        - RELATED_TO: Same domain/topic overlap

    Args:
        knowledge: List of knowledge objects to analyze.

    Returns:
        List of detected relations.
    """
    relations: list[KnowledgeRelation] = []

    for i, k1 in enumerate(knowledge):
        for k2 in knowledge[i + 1:]:
            # Check for contradictions
            if _detect_contradiction(k1, k2):
                relations.append(KnowledgeRelation(
                    source_id=k1.id,
                    target_id=k2.id,
                    relation_type="CONTRADICTS",
                    confidence=0.9,
                ))
            # Check for support (high similarity, same type)
            elif k1.knowledge_type == k2.knowledge_type:
                sim = jaccard_similarity(k1.content, k2.content)
                if sim >= 0.5:
                    relations.append(KnowledgeRelation(
                        source_id=k1.id,
                        target_id=k2.id,
                        relation_type="SUPPORTS",
                        confidence=sim,
                    ))
            # Check for topic overlap
            elif _topic_overlap(k1, k2):
                relations.append(KnowledgeRelation(
                    source_id=k1.id,
                    target_id=k2.id,
                    relation_type="RELATED_TO",
                    confidence=0.6,
                ))

    return relations


def find_contradictions(knowledge: list[KnowledgeObject]) -> list[tuple[str, str]]:
    """Find knowledge pairs that contradict each other.

    Args:
        knowledge: List of knowledge objects to analyze.

    Returns:
        List of (knowledge_id_1, knowledge_id_2) contradicting pairs.
    """
    contradictions: list[tuple[str, str]] = []

    for i, k1 in enumerate(knowledge):
        for k2 in knowledge[i + 1:]:
            if _detect_contradiction(k1, k2):
                contradictions.append((k1.id, k2.id))

    return contradictions


def build_derivation_chain(knowledge: list[KnowledgeObject]) -> dict[str, list[str]]:
    """Map each knowledge to what it was derived from.

    Args:
        knowledge: List of knowledge objects.

    Returns:
        Dict mapping knowledge_id to list of source knowledge_ids.
    """
    chain: dict[str, list[str]] = {}

    for k in knowledge:
        # Derivation is based on shared supporting memories
        sources = []
        for other in knowledge:
            if other.id == k.id:
                continue
            shared = set(k.supporting_memory_ids) & set(other.supporting_memory_ids)
            if shared:
                sources.append(other.id)
        chain[k.id] = sources

    return chain


def _detect_contradiction(k1: KnowledgeObject, k2: KnowledgeObject) -> bool:
    """Detect if two knowledge objects contradict each other.

    Uses the same patterns as continuity_metrics.detect_contradiction.
    """
    from relay.evaluation.continuity_metrics import detect_contradiction
    return detect_contradiction(k1.content, k2.content)


def _topic_overlap(k1: KnowledgeObject, k2: KnowledgeObject) -> bool:
    """Check if two knowledge objects share topic overlap."""
    # Domain match
    if k1.knowledge_domain == k2.knowledge_domain:
        return True

    # Tag overlap
    shared_tags = set(k1.tags) & set(k2.tags)
    if len(shared_tags) >= 2:
        return True

    # Content similarity threshold
    sim = jaccard_similarity(k1.content, k2.content)
    return sim >= 0.3
