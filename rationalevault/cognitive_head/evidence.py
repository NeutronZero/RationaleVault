from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from rationalevault.projections.knowledge import KnowledgeState

@dataclass(frozen=True)
class EvidenceBundle:
    concept_id: str
    title: str
    content: str
    supporting_evidence: list[str]  # e.g., memory IDs
    contradicting_evidence: list[str]  # e.g., contradicting memory/finding IDs
    provenance: list[str]  # source event IDs
    freshness: float  # days since last update
    source_diversity: int  # count of unique projects/sources
    base_confidence: float  # average confidence score from projections
    contradiction_findings: list[Any] = field(default_factory=list)

class EvidenceAggregator:
    @staticmethod
    def aggregate(knowledge_states: list[KnowledgeState]) -> list[EvidenceBundle]:
        concept_bundles: dict[str, dict[str, Any]] = {}

        # 1. Group active knowledge objects across states by normalized title
        for state in sorted(knowledge_states, key=lambda s: s.project_id):
            for k in state.active_knowledge:
                norm_title = " ".join(k.title.lower().strip().split())
                if norm_title not in concept_bundles:
                    concept_bundles[norm_title] = {
                        "concept_id": k.id,
                        "title": k.title,
                        "content": k.content,
                        "supporting_evidence": set(),
                        "contradicting_evidence": set(),
                        "provenance": set(),
                        "project_ids": set(),
                        "confidences": [],
                        "created_ats": [],
                        "updated_ats": [],
                        "contradiction_findings": []
                    }
                
                bundle = concept_bundles[norm_title]
                bundle["supporting_evidence"].update(k.supporting_memory_ids)
                bundle["contradicting_evidence"].update(k.contradicting_memory_ids)
                if k.provenance and k.provenance.source_event_ids:
                    bundle["provenance"].update(k.provenance.source_event_ids)
                bundle["project_ids"].add(k.project_id)
                bundle["confidences"].append(k.confidence.score)
                bundle["created_ats"].append(k.created_at)
                bundle["updated_ats"].append(k.updated_at)

        # 2. Gather matching contradiction records from state conflict queues
        for state in sorted(knowledge_states, key=lambda s: s.project_id):
            for conflict in state.conflict_queue:
                norm_a = " ".join(conflict.knowledge_a_title.lower().strip().split())
                norm_b = " ".join(conflict.knowledge_b_title.lower().strip().split())
                if norm_a in concept_bundles:
                    concept_bundles[norm_a]["contradiction_findings"].append(conflict)
                if norm_b in concept_bundles:
                    concept_bundles[norm_b]["contradiction_findings"].append(conflict)

        # 3. Build and return EvidenceBundles
        from datetime import datetime, timezone
        bundles = []
        for norm_title, data in sorted(concept_bundles.items()):
            newest_update = None
            for t_str in data["updated_ats"]:
                try:
                    t = datetime.fromisoformat(t_str)
                    if newest_update is None or t > newest_update:
                        newest_update = t
                except Exception:
                    pass

            if newest_update:
                if newest_update.tzinfo is None:
                    newest_update = newest_update.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                age_days = (now - newest_update).total_seconds() / 86400.0
            else:
                age_days = 0.0

            avg_conf = sum(data["confidences"]) / len(data["confidences"]) if data["confidences"] else 0.0

            bundles.append(EvidenceBundle(
                concept_id=data["concept_id"],
                title=data["title"],
                content=data["content"],
                supporting_evidence=sorted(list(data["supporting_evidence"])),
                contradicting_evidence=sorted(list(data["contradicting_evidence"])),
                provenance=sorted(list(data["provenance"])),
                freshness=max(0.0, age_days),
                source_diversity=len(data["project_ids"]),
                base_confidence=avg_conf,
                contradiction_findings=data["contradiction_findings"]
            ))

        return bundles
