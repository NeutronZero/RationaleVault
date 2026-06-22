from __future__ import annotations

import hashlib
from dataclasses import dataclass
import uuid
from relay.memory.factory import get_memory_provider
from relay.db.event_store import EventStore
from relay.schema.events import EventMetadata, EventType


@dataclass
class ConsolidationCandidate:
    candidate_id: str
    memory_ids: list[str]
    similarity_score: float
    cluster_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "memory_ids": self.memory_ids,
            "similarity_score": self.similarity_score,
            "cluster_size": self.cluster_size,
        }


def jaccard_similarity(text1: str, text2: str) -> float:
    words1 = set(text1.lower().strip().split())
    words2 = set(text2.lower().strip().split())
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


def detect_consolidation_candidates() -> list[ConsolidationCandidate]:
    """
    Scans active memories of the same type and groups them into duplicate clusters
    if their token-based Jaccard similarity is >= 0.35.
    Returns list of ConsolidationCandidate structures (no actual merge performed).
    """
    provider = get_memory_provider()
    records = provider.get_all_records()
    
    active_records = [r for r in records if r.lifecycle_status.lower() == "active"]
    candidates = []
    visited = set()
    
    for i, r1 in enumerate(active_records):
        if r1.id in visited:
            continue
        cluster = [r1]
        for r2 in active_records[i+1:]:
            if r2.id in visited:
                continue
            if r1.memory_type == r2.memory_type:
                sim = jaccard_similarity(r1.content, r2.content)
                if sim >= 0.35:
                    cluster.append(r2)
                    
        if len(cluster) > 1:
            for c in cluster:
                visited.add(c.id)
            
            sorted_ids = sorted([c.id for c in cluster])
            cand_id = hashlib.sha256((":".join(sorted_ids)).encode("utf-8")).hexdigest()
            
            # Average similarity score
            sims = []
            for idx, c1 in enumerate(cluster):
                for c2 in cluster[idx+1:]:
                    sims.append(jaccard_similarity(c1.content, c2.content))
            avg_sim = sum(sims) / len(sims) if sims else 1.0
            
            candidates.append(
                ConsolidationCandidate(
                    candidate_id=cand_id,
                    memory_ids=sorted_ids,
                    similarity_score=avg_sim,
                    cluster_size=len(cluster)
                )
            )
            
    return candidates


def emit_consolidation_candidates(project_id: uuid.UUID) -> int:
    """
    Detects candidates and logs CONSOLIDATION_CANDIDATE events to the event ledger.
    """
    candidates = detect_consolidation_candidates()
    if not candidates:
        return 0
    try:
        store = EventStore()
        metadata = EventMetadata(actor="consolidation_detector", source="consolidation_engine")
        for cand in candidates:
            store.append_event(
                project_id=project_id,
                stream_id="consolidation_candidates",
                event_type=EventType.CONSOLIDATION_CANDIDATE,
                payload={
                    "candidate_id": cand.candidate_id,
                    "memory_ids": cand.memory_ids,
                    "similarity_score": cand.similarity_score,
                    "cluster_size": cand.cluster_size
                },
                metadata=metadata
            )
    except Exception:
        pass
    return len(candidates)
