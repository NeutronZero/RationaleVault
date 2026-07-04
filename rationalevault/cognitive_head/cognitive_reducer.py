from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from rationalevault.projections.knowledge import KnowledgeState


@dataclass(frozen=True)
class CognitiveReduction:
    invariants: list[str]  # titles of invariants
    supporting_evidence: list[str]  # IDs of supporting memories
    conflicting_evidence: list[str]  # IDs of contradicting memories
    confidence: float
    unresolved_questions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "invariants": self.invariants,
            "supporting_evidence": self.supporting_evidence,
            "conflicting_evidence": self.conflicting_evidence,
            "confidence": self.confidence,
            "unresolved_questions": self.unresolved_questions,
        }


class CognitiveStateReducer:
    """Aggregates and summarizes cross-repository constraints and invariants deterministically."""

    @staticmethod
    def reduce(knowledge_states: list[KnowledgeState]) -> CognitiveReduction:
        invariants = []
        supporting_evidence = []
        conflicting_evidence = []
        total_confidence = 0.0
        confidence_count = 0
        unresolved_questions = []

        # Sort the knowledge states deterministically by project_id to ensure order invariance
        for state in sorted(knowledge_states, key=lambda s: s.project_id):
            for inv in state.invariants:
                if inv.title not in invariants:
                    invariants.append(inv.title)
                supporting_evidence.extend(inv.supporting_memory_ids)
                conflicting_evidence.extend(inv.contradicting_memory_ids)
                total_confidence += inv.confidence.score
                confidence_count += 1

            for conflict in state.conflict_queue:
                q_text = f"Resolve contradiction: {conflict.knowledge_a_title} vs {conflict.knowledge_b_title}"
                if q_text not in unresolved_questions:
                    unresolved_questions.append(q_text)

        # Remove duplicates while preserving deterministic order
        seen_sup = set()
        supporting_evidence = [x for x in supporting_evidence if not (x in seen_sup or seen_sup.add(x))]
        seen_conf = set()
        conflicting_evidence = [x for x in conflicting_evidence if not (x in seen_conf or seen_conf.add(x))]

        avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 1.0

        return CognitiveReduction(
            invariants=invariants,
            supporting_evidence=supporting_evidence,
            conflicting_evidence=conflicting_evidence,
            confidence=avg_confidence,
            unresolved_questions=unresolved_questions,
        )
