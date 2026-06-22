"""Relay Knowledge Synthesizer — Core synthesis engine.

Deterministic, no LLM dependency. All synthesis is traceable back to
source memories and source events.

Workflow patterns are normalized through memories first:
    Events → WORKFLOW memory → WORKFLOW_PATTERN knowledge

This ensures provenance consistency across all knowledge types.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Optional

from relay.knowledge.models import (
    ArchitecturePrinciple,
    KnowledgeConfidence,
    KnowledgeDomain,
    KnowledgeLifecycle,
    KnowledgeObject,
    KnowledgeType,
    ProjectInvariant,
    ProvenanceChain,
    generate_knowledge_id,
)
from relay.knowledge.lineage import build_provenance_chain
from relay.memory.consolidation import jaccard_similarity
from relay.memory.models import MemoryRecord, MemoryType


def synthesize_all(
    project_id: uuid.UUID,
    existing_knowledge: Optional[list[KnowledgeObject]] = None,
) -> list[KnowledgeObject]:
    """Main entry point: scan all memories and produce knowledge objects.

    This is an explicit projection step, NOT automatic on append_event.
    Knowledge synthesis is triggered via:
        - relay knowledge synthesize
        - run_handoff_suite()

    Args:
        project_id: The project UUID.
        existing_knowledge: Previously synthesized knowledge (for STALE detection).

    Returns:
        List of synthesized knowledge objects.
    """
    from relay.memory.factory import get_memory_provider

    provider = get_memory_provider()
    memories = provider.get_all_records()

    knowledge: list[KnowledgeObject] = []
    knowledge.extend(_detect_project_invariants(memories))
    knowledge.extend(_detect_architecture_principles(memories))
    knowledge.extend(_detect_lessons(memories))
    knowledge.extend(_detect_failure_patterns(memories))
    knowledge.extend(_detect_workflow_patterns(memories))
    knowledge.extend(_detect_research_findings(memories))
    knowledge.extend(_build_decision_lineage(memories))

    # Mark existing STALE knowledge
    if existing_knowledge:
        _mark_stale_knowledge(knowledge, existing_knowledge)

    return knowledge


def _detect_project_invariants(memories: list[MemoryRecord]) -> list[ProjectInvariant]:
    """Detect project invariants from critical architecture memories.

    Project invariants are not architecture decisions — they are fundamental
    truths about the project that never change.
    """
    # Look for memories tagged with invariant-related tags
    invariant_tags = {"invariant", "always", "never", "required", "must"}
    invariants: list[ProjectInvariant] = []

    for mem in memories:
        if mem.memory_type != MemoryType.ARCHITECTURE:
            continue
        if mem.importance != "critical":
            continue

        # Check if content suggests invariant
        content_lower = mem.content.lower()
        is_invariant = (
            "must" in content_lower
            or "never" in content_lower
            or "always" in content_lower
            or "required" in content_lower
            or any(tag in invariant_tags for tag in mem.tags)
        )

        if not is_invariant:
            continue

        confidence = _compute_confidence([mem])
        k_id = generate_knowledge_id(
            KnowledgeType.PROJECT_INVARIANT.value, mem.title, mem.content
        )

        provenance = ProvenanceChain(
            knowledge_id=k_id,
            source_memory_ids=[mem.id],
            source_event_ids=mem.source_event_ids,
            synthesis_event_id="",
            confidence=confidence,
            evidence_count=1,
        )

        invariants.append(ProjectInvariant(
            id=k_id,
            version=1,
            title=mem.title,
            content=mem.content,
            knowledge_type=KnowledgeType.PROJECT_INVARIANT,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=confidence,
            importance="critical",
            provenance=provenance,
            tags=mem.tags + ["invariant"],
            supporting_memory_ids=[mem.id],
        ))

    return invariants


def _detect_architecture_principles(memories: list[MemoryRecord]) -> list[ArchitecturePrinciple]:
    """Cluster ARCHITECTURE memories by Jaccard similarity ≥ 0.4.

    Returns ArchitecturePrinciple objects with supporting decisions.
    """
    arch_memories = [m for m in memories if m.memory_type == MemoryType.ARCHITECTURE]
    clusters = _cluster_by_similarity(arch_memories, threshold=0.4)

    principles: list[ArchitecturePrinciple] = []

    # Handle single memories that didn't cluster
    clustered_ids = {m.id for cluster in clusters for m in cluster}
    for mem in arch_memories:
        if mem.id not in clustered_ids:
            clusters.append([mem])

    for cluster in clusters:
        content = _merge_cluster_content(cluster)
        title = _extract_principal_title(cluster)
        confidence = _compute_confidence(cluster)

        # Find supporting decisions and rationales
        supporting_decisions: list[str] = []
        supporting_rationales: list[str] = []
        for m in memories:
            if m.memory_type == MemoryType.DECISION:
                if _overlaps_with_cluster(m, cluster):
                    supporting_decisions.append(m.content)
            if m.memory_type == MemoryType.DECISION_RATIONALE:
                if _overlaps_with_cluster(m, cluster):
                    supporting_rationales.append(m.content)

        principle_strength = confidence.score
        k_id = generate_knowledge_id(
            KnowledgeType.ARCHITECTURE_PRINCIPLE.value, title, content
        )

        provenance = ProvenanceChain(
            knowledge_id=k_id,
            source_memory_ids=[m.id for m in cluster],
            source_event_ids=_collect_event_ids(cluster),
            synthesis_event_id="",
            confidence=confidence,
            evidence_count=len(cluster),
        )

        principles.append(ArchitecturePrinciple(
            id=k_id,
            version=1,
            title=title,
            content=content,
            knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=confidence,
            importance="critical",
            provenance=provenance,
            tags=_extract_tags(cluster),
            supporting_memory_ids=[m.id for m in cluster],
            supporting_decisions=supporting_decisions,
            supporting_rationales=supporting_rationales,
            principle_strength=principle_strength,
        ))

    return principles


def _detect_lessons(memories: list[MemoryRecord]) -> list[KnowledgeObject]:
    """Cluster LESSON_LEARNED memories by topic similarity."""
    lesson_memories = [m for m in memories if m.memory_type == MemoryType.LESSON_LEARNED]
    clusters = _cluster_by_similarity(lesson_memories, threshold=0.35)

    lessons: list[KnowledgeObject] = []
    for cluster in clusters:
        content = _merge_cluster_content(cluster)
        title = _extract_principal_title(cluster)
        confidence = _compute_confidence(cluster)
        k_id = generate_knowledge_id(
            KnowledgeType.LESSON.value, title, content
        )

        provenance = ProvenanceChain(
            knowledge_id=k_id,
            source_memory_ids=[m.id for m in cluster],
            source_event_ids=_collect_event_ids(cluster),
            synthesis_event_id="",
            confidence=confidence,
            evidence_count=len(cluster),
        )

        lessons.append(KnowledgeObject(
            id=k_id,
            version=1,
            title=title,
            content=content,
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            confidence=confidence,
            importance="medium",
            provenance=provenance,
            tags=_extract_tags(cluster),
            supporting_memory_ids=[m.id for m in cluster],
        ))

    return lessons


def _detect_failure_patterns(memories: list[MemoryRecord]) -> list[KnowledgeObject]:
    """Group FAILURE memories into patterns."""
    failure_memories = [m for m in memories if m.memory_type == MemoryType.FAILURE]
    clusters = _cluster_by_similarity(failure_memories, threshold=0.35)

    patterns: list[KnowledgeObject] = []
    for cluster in clusters:
        content = _merge_cluster_content(cluster)
        title = _extract_principal_title(cluster)
        confidence = _compute_confidence(cluster)
        k_id = generate_knowledge_id(
            KnowledgeType.FAILURE_PATTERN.value, title, content
        )

        provenance = ProvenanceChain(
            knowledge_id=k_id,
            source_memory_ids=[m.id for m in cluster],
            source_event_ids=_collect_event_ids(cluster),
            synthesis_event_id="",
            confidence=confidence,
            evidence_count=len(cluster),
        )

        patterns.append(KnowledgeObject(
            id=k_id,
            version=1,
            title=title,
            content=content,
            knowledge_type=KnowledgeType.FAILURE_PATTERN,
            knowledge_domain=KnowledgeDomain.QUALITY,
            confidence=confidence,
            importance="high",
            provenance=provenance,
            tags=_extract_tags(cluster),
            supporting_memory_ids=[m.id for m in cluster],
        ))

    return patterns


def _detect_workflow_patterns(memories: list[MemoryRecord]) -> list[KnowledgeObject]:
    """Detect WORKFLOW memories and synthesize into WORKFLOW_PATTERN knowledge.

    This follows the normalized pattern:
        Events → WORKFLOW memory → WORKFLOW_PATTERN knowledge

    Ensures provenance consistency across all knowledge types.
    """
    workflow_memories = [m for m in memories if m.memory_type == MemoryType.WORKFLOW]
    clusters = _cluster_by_similarity(workflow_memories, threshold=0.35)

    patterns: list[KnowledgeObject] = []
    for cluster in clusters:
        content = _merge_cluster_content(cluster)
        title = _extract_principal_title(cluster)
        confidence = _compute_confidence(cluster)
        k_id = generate_knowledge_id(
            KnowledgeType.WORKFLOW_PATTERN.value, title, content
        )

        provenance = ProvenanceChain(
            knowledge_id=k_id,
            source_memory_ids=[m.id for m in cluster],
            source_event_ids=_collect_event_ids(cluster),
            synthesis_event_id="",
            confidence=confidence,
            evidence_count=len(cluster),
        )

        patterns.append(KnowledgeObject(
            id=k_id,
            version=1,
            title=title,
            content=content,
            knowledge_type=KnowledgeType.WORKFLOW_PATTERN,
            knowledge_domain=KnowledgeDomain.PROCESS,
            confidence=confidence,
            importance="medium",
            provenance=provenance,
            tags=_extract_tags(cluster),
            supporting_memory_ids=[m.id for m in cluster],
        ))

    return patterns


def _detect_research_findings(memories: list[MemoryRecord]) -> list[KnowledgeObject]:
    """Consolidate RESEARCH memories on same topic."""
    research_memories = [m for m in memories if m.memory_type == MemoryType.RESEARCH]
    clusters = _cluster_by_similarity(research_memories, threshold=0.4)

    findings: list[KnowledgeObject] = []
    for cluster in clusters:
        content = _merge_cluster_content(cluster)
        title = _extract_principal_title(cluster)
        confidence = _compute_confidence(cluster)
        k_id = generate_knowledge_id(
            KnowledgeType.RESEARCH_FINDING.value, title, content
        )

        provenance = ProvenanceChain(
            knowledge_id=k_id,
            source_memory_ids=[m.id for m in cluster],
            source_event_ids=_collect_event_ids(cluster),
            synthesis_event_id="",
            confidence=confidence,
            evidence_count=len(cluster),
        )

        findings.append(KnowledgeObject(
            id=k_id,
            version=1,
            title=title,
            content=content,
            knowledge_type=KnowledgeType.RESEARCH_FINDING,
            knowledge_domain=KnowledgeDomain.RESEARCH,
            confidence=confidence,
            importance="medium",
            provenance=provenance,
            tags=_extract_tags(cluster),
            supporting_memory_ids=[m.id for m in cluster],
        ))

    return findings


def _build_decision_lineage(memories: list[MemoryRecord]) -> list[KnowledgeObject]:
    """Chain decisions with their rationales and supersessions."""
    decisions = [m for m in memories if m.memory_type == MemoryType.DECISION]
    rationales = [m for m in memories if m.memory_type == MemoryType.DECISION_RATIONALE]

    lineage_objects: list[KnowledgeObject] = []
    for dec in decisions:
        rationale = _find_matching_rationale(dec, rationales)
        content = f"Decision: {dec.content}"
        if rationale:
            content += f"\nRationale: {rationale.content}"

        source_memories = [dec] + ([rationale] if rationale else [])
        confidence = _compute_confidence(source_memories)
        k_id = generate_knowledge_id(
            KnowledgeType.DECISION_LINEAGE.value, dec.title, content
        )

        provenance = ProvenanceChain(
            knowledge_id=k_id,
            source_memory_ids=[dec.id] + ([rationale.id] if rationale else []),
            source_event_ids=dec.source_event_ids,
            synthesis_event_id="",
            confidence=confidence,
            evidence_count=1 + (1 if rationale else 0),
        )

        lineage_objects.append(KnowledgeObject(
            id=k_id,
            version=1,
            title=f"Decision Lineage: {dec.title}",
            content=content,
            knowledge_type=KnowledgeType.DECISION_LINEAGE,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=confidence,
            importance=dec.importance,
            provenance=provenance,
            tags=dec.tags,
            supporting_memory_ids=[dec.id] + ([rationale.id] if rationale else []),
        ))

    return lineage_objects


# ── Helper Functions ──────────────────────────────────────────────────────────


def _compute_confidence(memories: list[MemoryRecord]) -> KnowledgeConfidence:
    """Derive confidence from evidence."""
    if not memories:
        return KnowledgeConfidence(0, 0, 0, 0.0, 0.0)

    all_event_ids: list[str] = []
    for m in memories:
        all_event_ids.extend(m.source_event_ids)

    avg_conf = sum(m.confidence for m in memories) / len(memories)

    return KnowledgeConfidence(
        memory_count=len(memories),
        source_event_count=len(set(all_event_ids)),
        contradiction_count=0,
        average_memory_confidence=avg_conf,
    )


def _cluster_by_similarity(
    memories: list[MemoryRecord], threshold: float
) -> list[list[MemoryRecord]]:
    """Jaccard-based clustering (same pattern as consolidation.py)."""
    clusters: list[list[MemoryRecord]] = []
    visited: set[str] = set()

    for i, m1 in enumerate(memories):
        if m1.id in visited:
            continue
        cluster = [m1]
        for m2 in memories[i + 1 :]:
            if m2.id in visited:
                continue
            sim = jaccard_similarity(m1.content, m2.content)
            if sim >= threshold:
                cluster.append(m2)
        if len(cluster) > 1:
            for c in cluster:
                visited.add(c.id)
            clusters.append(cluster)

    return clusters


def _merge_cluster_content(cluster: list[MemoryRecord]) -> str:
    """Merge cluster content into a single knowledge description."""
    if len(cluster) == 1:
        return cluster[0].content

    parts = []
    for i, mem in enumerate(cluster):
        parts.append(f"{i + 1}. {mem.content}")
    return "\n".join(parts)


def _extract_principal_title(cluster: list[MemoryRecord]) -> str:
    """Extract a representative title from a cluster."""
    if len(cluster) == 1:
        return cluster[0].title

    # Use the most important memory's title
    importance_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_cluster = sorted(
        cluster,
        key=lambda m: importance_order.get(m.importance.lower(), 2),
    )
    return sorted_cluster[0].title


def _extract_tags(cluster: list[MemoryRecord]) -> list[str]:
    """Extract unique tags from a cluster."""
    tags: set[str] = set()
    for mem in cluster:
        tags.update(mem.tags)
    return sorted(tags)


def _collect_event_ids(cluster: list[MemoryRecord]) -> list[str]:
    """Collect all source event IDs from a cluster."""
    event_ids: list[str] = []
    for mem in cluster:
        event_ids.extend(mem.source_event_ids)
    return list(set(event_ids))


def _overlaps_with_cluster(memory: MemoryRecord, cluster: list[MemoryRecord]) -> bool:
    """Check if a memory overlaps with a cluster's content."""
    for mem in cluster:
        sim = jaccard_similarity(memory.content, mem.content)
        if sim >= 0.3:
            return True
    return False


def _find_matching_rationale(
    decision: MemoryRecord, rationales: list[MemoryRecord]
) -> Optional[MemoryRecord]:
    """Find the rationale that matches a decision."""
    for rat in rationales:
        # Check if rationale was recorded near the same time or references the decision
        if decision.id in rat.source_event_ids:
            return rat
        # Fallback: check content similarity
        sim = jaccard_similarity(decision.content, rat.content)
        if sim >= 0.2:
            return rat
    return None


def _mark_stale_knowledge(
    current: list[KnowledgeObject],
    existing: list[KnowledgeObject],
) -> None:
    """Mark existing knowledge as STALE if its source memories have changed."""
    current_memory_ids = set()
    for k in current:
        current_memory_ids.update(k.supporting_memory_ids)

    for existing_k in existing:
        # If any supporting memory is no longer in current synthesis, mark STALE
        if not set(existing_k.supporting_memory_ids) & current_memory_ids:
            existing_k.lifecycle_status = KnowledgeLifecycle.STALE.value
            existing_k.updated_at = datetime.now().isoformat()
