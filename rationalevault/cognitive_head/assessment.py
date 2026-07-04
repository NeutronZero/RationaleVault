from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from rationalevault.cognitive_head.evidence import EvidenceBundle
from rationalevault.cognitive_head.config import ReasoningConfig

@dataclass(frozen=True)
class EvidenceAssessment:
    base_confidence: float
    agreement_score: float
    corroboration_score: float
    contradiction_penalty: float
    staleness_penalty: float
    propagated_adjustment: float
    local_confidence: float
    final_confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_confidence": round(self.base_confidence, 4),
            "agreement_score": round(self.agreement_score, 4),
            "corroboration_score": round(self.corroboration_score, 4),
            "contradiction_penalty": round(self.contradiction_penalty, 4),
            "staleness_penalty": round(self.staleness_penalty, 4),
            "propagated_adjustment": round(self.propagated_adjustment, 4),
            "local_confidence": round(self.local_confidence, 4),
            "final_confidence": round(self.final_confidence, 4),
        }

class AssessmentEngine:
    @staticmethod
    def assess(bundle: EvidenceBundle, config: ReasoningConfig = ReasoningConfig()) -> EvidenceAssessment:
        # 1. Base confidence
        base = bundle.base_confidence

        # 2. Agreement score (source diversity bonus)
        agreement = min(0.2, max(0.0, (bundle.source_diversity - 1) * config.agreement_weight))

        # 3. Corroboration score (supporting evidence count bonus)
        corroboration = min(0.2, max(0.0, len(bundle.supporting_evidence) * config.corroboration_weight))

        # 4. Contradiction penalty
        num_contradictions = len(bundle.contradicting_evidence) + len(bundle.contradiction_findings)
        contradiction_penalty = min(1.0, max(0.0, num_contradictions * config.contradiction_penalty_weight))

        # 5. Staleness penalty
        staleness_penalty = min(0.5, max(0.0, bundle.freshness * config.staleness_penalty_weight))

        # 6. Compute local confidence
        local_confidence = base + agreement + corroboration - contradiction_penalty - staleness_penalty
        local_confidence = max(0.0, min(1.0, local_confidence))

        # Final confidence initially matches local before propagation
        final_confidence = local_confidence

        return EvidenceAssessment(
            base_confidence=base,
            agreement_score=agreement,
            corroboration_score=corroboration,
            contradiction_penalty=contradiction_penalty,
            staleness_penalty=staleness_penalty,
            propagated_adjustment=0.0,
            local_confidence=local_confidence,
            final_confidence=final_confidence
        )
