"""
RationaleVault Knowledge Materialization — Converts KnowledgeCandidate into KnowledgeObject.

This is the final step in the promotion pipeline:

    KnowledgeCandidate → KnowledgeObject

The materializer:
  1. Maps candidate fields to KnowledgeObject fields
  2. Builds ProvenanceChain from source references
  3. Computes KnowledgeConfidence from evidence
  4. Sets initial epistemic status (PROPOSED for new knowledge)

Design rules:
  - Deterministic — no randomness, no I/O, no AI calls.
  - KnowledgeObject is the authoritative queryable state.
  - Lineage is reconstructed from projections, not stored redundantly.
"""
from __future__ import annotations

from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeLifecycle,
    KnowledgeConfidence,
    ProvenanceChain,
    EpistemicStatus,
)
from rationalevault.knowledge.promotion_models import (
    KnowledgeCandidate,
    KnowledgePromotionDecision,
)


class KnowledgeMaterializer:
    """
    Converts a KnowledgeCandidate into a KnowledgeObject.

    This is the final deterministic step before knowledge becomes queryable state.
    """

    @staticmethod
    def materialize(
        candidate: KnowledgeCandidate,
        decision: KnowledgePromotionDecision,
        project_id: str = "",
    ) -> KnowledgeObject:
        """
        Materialize a KnowledgeCandidate into a KnowledgeObject.

        Args:
            candidate: The approved KnowledgeCandidate.
            decision: The approval decision (for provenance).
            project_id: Optional project identifier.

        Returns:
            A fully-formed KnowledgeObject ready for storage.
        """
        # Compute confidence from evidence
        supporting = len(candidate.supporting_memory_ids)
        contradicting = len(candidate.contradicting_memory_ids)
        confidence = KnowledgeConfidence(
            memory_count=supporting,
            source_event_count=len(candidate.source_reflection_ids) + len(candidate.source_learning_record_ids),
            contradiction_count=contradicting,
            average_memory_confidence=candidate.confidence,
        )

        # Build provenance chain
        provenance = ProvenanceChain(
            knowledge_id="",  # Will be set after ID generation
            source_memory_ids=list(candidate.supporting_memory_ids),
            source_event_ids=list(candidate.source_reflection_ids),
            synthesis_event_id=decision.decision_id,
            confidence=confidence,
            evidence_count=supporting,
        )

        # Generate deterministic knowledge ID
        from rationalevault.knowledge.models import generate_knowledge_id
        knowledge_id = generate_knowledge_id(
            candidate.knowledge_type.value,
            candidate.title,
            candidate.content,
            project_id,
        )

        # Set provenance knowledge_id
        provenance = ProvenanceChain(
            knowledge_id=knowledge_id,
            source_memory_ids=provenance.source_memory_ids,
            source_event_ids=provenance.source_event_ids,
            synthesis_event_id=provenance.synthesis_event_id,
            confidence=provenance.confidence,
            evidence_count=provenance.evidence_count,
        )

        # Determine initial epistemic status based on evidence
        epistemic_status = _determine_initial_status(
            candidate.confidence,
            supporting,
            contradicting,
        )

        # Create the KnowledgeObject
        knowledge = KnowledgeObject(
            id=knowledge_id,
            version=1,
            title=candidate.title,
            content=candidate.content,
            knowledge_type=candidate.knowledge_type,
            knowledge_domain=candidate.knowledge_domain,
            confidence=confidence,
            importance=candidate.importance,
            provenance=provenance,
            tags=[],
            supporting_memory_ids=list(candidate.supporting_memory_ids),
            contradicting_memory_ids=list(candidate.contradicting_memory_ids),
            lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
            superseded_by=None,
            created_at=candidate.created_at,
            updated_at=candidate.created_at,
            project_id=project_id,
            transferability=candidate.transferability.value,
            epistemic_status=epistemic_status,
        )

        return knowledge


def _determine_initial_status(
    confidence: float,
    supporting: int,
    contradicting: int,
) -> EpistemicStatus:
    """
    Deterministically classify initial epistemic status.

    Rules:
      - No contradictions + high confidence → VALIDATED
      - No contradictions + medium confidence → PROPOSED
      - Has contradictions → CONFLICTED
    """
    if contradicting > 0:
        return EpistemicStatus.CONFLICTED
    elif confidence >= 0.8 and supporting >= 3:
        return EpistemicStatus.VALIDATED
    else:
        return EpistemicStatus.PROPOSED
