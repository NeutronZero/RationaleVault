from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from rationalevault.cognitive_head.belief import Belief
from rationalevault.cognitive_head.assessment import EvidenceAssessment
from rationalevault.cognitive_head.config import ReasoningConfig
from rationalevault.knowledge.contradiction import ContradictionFinding

@dataclass(frozen=True)
class ReasoningReport:
    beliefs: list[Belief]
    assessments: list[EvidenceAssessment]
    contradictions: list[ContradictionFinding]
    summary: dict[str, Any]
    overall_confidence: float
    reasoning_version: str
    config_snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "beliefs": [b.to_dict() for b in self.beliefs],
            "assessments": [a.to_dict() for a in self.assessments],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "summary": self.summary,
            "overall_confidence": round(self.overall_confidence, 4),
            "reasoning_version": self.reasoning_version,
            "config_snapshot": self.config_snapshot,
        }

class ReasoningReportBuilder:
    @staticmethod
    def build(
        beliefs: list[Belief],
        contradictions: list[ContradictionFinding],
        config: ReasoningConfig = ReasoningConfig()
    ) -> ReasoningReport:
        assessments = [b.assessment for b in beliefs]
        
        total_rules = len(beliefs)
        invariants = 0
        validated = 0
        conflicted = 0
        superseded = 0
        archived = 0

        for b in beliefs:
            has_contradiction = any(c.rule_a_id == b.supporting_evidence[0] or c.rule_b_id == b.supporting_evidence[0] 
                                    for c in contradictions if not getattr(c, "suppressed", False))
            
            if has_contradiction:
                conflicted += 1
            elif b.final_confidence >= 0.95:
                invariants += 1
            elif b.final_confidence >= 0.7:
                validated += 1
            
        active_contradictions = [c for c in contradictions if not getattr(c, "suppressed", False)]

        summary = {
            "total_rules": total_rules,
            "invariants": invariants,
            "validated": validated,
            "conflicted": conflicted,
            "superseded": superseded,
            "archived": archived,
            "contradictions_count": len(contradictions),
            "active_contradictions_count": len(active_contradictions),
        }

        overall_conf = sum(b.final_confidence for b in beliefs) / len(beliefs) if beliefs else 1.0

        config_snapshot = {
            "attenuation": config.attenuation,
            "agreement_weight": config.agreement_weight,
            "corroboration_weight": config.corroboration_weight,
            "contradiction_penalty_weight": config.contradiction_penalty_weight,
            "staleness_penalty_weight": config.staleness_penalty_weight,
        }

        return ReasoningReport(
            beliefs=beliefs,
            assessments=assessments,
            contradictions=contradictions,
            summary=summary,
            overall_confidence=overall_conf,
            reasoning_version=config.version,
            config_snapshot=config_snapshot
        )
