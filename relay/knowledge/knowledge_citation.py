"""Relay Knowledge Citation — Explainable citation for knowledge retrieval results.

Mirrors the MemoryCitation pattern from relay/memory/citation_builder.py.
Every knowledge citation traces back to source events through provenance chains.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from relay.knowledge.models import KnowledgeObject


@dataclass
class KnowledgeScore:
    """Score breakdown for a knowledge retrieval result.

    Mirrors RetrievalScore from relay/memory/ranking.py.
    """
    total: float
    confidence: float
    evidence_strength: float
    recency: float
    importance_bonus: float
    relation_bonus: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "confidence": self.confidence,
            "evidence_strength": self.evidence_strength,
            "recency": self.recency,
            "importance_bonus": self.importance_bonus,
            "relation_bonus": self.relation_bonus,
        }


@dataclass
class KnowledgeCitation:
    """Explainable citation for a knowledge retrieval result.

    Mirrors MemoryCitation from relay/memory/citation_builder.py.
    """
    knowledge_id: str
    score: KnowledgeScore
    source_event_ids: list[str]
    source_memory_ids: list[str]
    reasons: list[str]
    retrieval_path: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "score": self.score.to_dict(),
            "source_event_ids": self.source_event_ids,
            "source_memory_ids": self.source_memory_ids,
            "reasons": self.reasons,
            "retrieval_path": self.retrieval_path,
        }


def compute_knowledge_score(
    knowledge: KnowledgeObject,
    keywords: list[str],
) -> KnowledgeScore:
    """Computes a retrieval score for a knowledge object.

    Mirrors compute_retrieval_score from relay/memory/ranking.py.
    Uses deterministic, explainable heuristics — no LLM dependency.
    """
    confidence = knowledge.confidence.score

    evidence_count = knowledge.provenance.evidence_count
    evidence_strength = math.log1p(evidence_count) / 3.0

    try:
        updated = datetime.fromisoformat(knowledge.updated_at)
        age_days = (datetime.now() - updated).total_seconds() / 86400.0
        recency = math.exp(-0.01155 * max(0.0, age_days))
    except Exception:
        recency = 1.0

    importance_map = {"critical": 5.0, "high": 3.0, "medium": 2.0, "low": 1.0}
    importance_bonus = importance_map.get(knowledge.importance.lower(), 2.0)

    supporting_count = len(knowledge.supporting_memory_ids)
    contradicting_count = len(knowledge.contradicting_memory_ids)
    relation_bonus = math.log1p(supporting_count) - (contradicting_count * 0.5)

    lifecycle_penalties = {
        "active": 0.0,
        "stale": -2.0,
        "superseded": -5.0,
        "archived": -10.0,
    }
    lifecycle_penalty = lifecycle_penalties.get(
        knowledge.lifecycle_status.lower(), 0.0
    )

    total = (
        confidence
        + evidence_strength
        + recency
        + importance_bonus
        + relation_bonus
        + lifecycle_penalty
    )

    return KnowledgeScore(
        total=total,
        confidence=confidence,
        evidence_strength=evidence_strength,
        recency=recency,
        importance_bonus=importance_bonus,
        relation_bonus=relation_bonus,
    )


def build_knowledge_citation(
    knowledge: KnowledgeObject,
    query: str,
    retrieval_path: list[str],
) -> KnowledgeCitation:
    """Constructs explainable knowledge citations from query terms and metadata.

    Mirrors build_citation from relay/memory/citation_builder.py.
    """
    keywords = extract_keywords(query)
    score = compute_knowledge_score(knowledge, keywords)

    reasons: list[str] = []
    q_clean = query.lower().strip() if query else ""

    if q_clean:
        if q_clean in knowledge.title.lower():
            reasons.append("keyword_match_title")
        if q_clean in knowledge.content.lower():
            reasons.append("keyword_match_content")

    if knowledge.confidence.score >= 0.9:
        reasons.append("high_confidence")

    if knowledge.importance == "critical":
        reasons.append("critical_importance")
    elif knowledge.importance == "high":
        reasons.append("high_importance")

    if knowledge.provenance.evidence_count >= 3:
        reasons.append("strong_evidence")

    if knowledge.contradicting_memory_ids:
        reasons.append("has_contradictions")

    if not reasons:
        reasons.append("general_relevance")

    return KnowledgeCitation(
        knowledge_id=knowledge.id,
        score=score,
        source_event_ids=knowledge.provenance.source_event_ids,
        source_memory_ids=knowledge.provenance.source_memory_ids,
        reasons=reasons,
        retrieval_path=retrieval_path,
    )


def extract_keywords(query: str) -> list[str]:
    """Extract keywords from query (same pattern as query_analyzer and semantic_search)."""
    q_clean = query.lower().strip()
    words = [w.strip("?,.:;\"'()[]{}") for w in q_clean.split()]
    stopwords = {
        "what", "is", "a", "the", "of", "and", "in", "to", "exist",
        "are", "about", "for", "with", "on", "exists", "did", "occur", "why",
    }
    return [w for w in words if w and w not in stopwords]
