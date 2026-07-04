from __future__ import annotations
import hashlib
from dataclasses import dataclass
from typing import Any
from rationalevault.cognitive_head.assessment import EvidenceAssessment

@dataclass
class Belief:
    belief_id: str
    title: str
    content: str
    local_confidence: float
    propagated_adjustment: float
    final_confidence: float
    assessment: EvidenceAssessment
    supporting_evidence: list[str]
    dependent_belief_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "belief_id": self.belief_id,
            "title": self.title,
            "content": self.content,
            "local_confidence": round(self.local_confidence, 4),
            "propagated_adjustment": round(self.propagated_adjustment, 4),
            "final_confidence": round(self.final_confidence, 4),
            "assessment": self.assessment.to_dict(),
            "supporting_evidence": self.supporting_evidence,
            "dependent_belief_ids": self.dependent_belief_ids,
        }

class BeliefEngine:
    @staticmethod
    def generate_belief_id(title: str, content: str) -> str:
        norm_title = " ".join(title.lower().strip().split())
        norm_content = " ".join(content.lower().strip().split())
        data = f"belief:{norm_title}:{norm_content}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"BEL-{h}"

    @staticmethod
    def construct(title: str, content: str, assessment: EvidenceAssessment, supporting_evidence: list[str]) -> Belief:
        belief_id = BeliefEngine.generate_belief_id(title, content)
        return Belief(
            belief_id=belief_id,
            title=title,
            content=content,
            local_confidence=assessment.local_confidence,
            propagated_adjustment=assessment.propagated_adjustment,
            final_confidence=assessment.final_confidence,
            assessment=assessment,
            supporting_evidence=supporting_evidence,
            dependent_belief_ids=[]
        )
