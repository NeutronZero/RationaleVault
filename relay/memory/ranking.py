from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from relay.memory.models import MemoryRecord


@dataclass
class RetrievalScore:
    total: float
    priority: float
    recency: float
    references: float
    confidence: float
    lifecycle_penalty: float

    def to_dict(self) -> dict[str, float]:
        return {
            "total": self.total,
            "priority": self.priority,
            "recency": self.recency,
            "references": self.references,
            "confidence": self.confidence,
            "lifecycle_penalty": self.lifecycle_penalty,
        }


def compute_retrieval_score(record: MemoryRecord) -> RetrievalScore:
    # 1. Priority Weight
    priority = record.retrieval_priority

    # 2. Recency Decay
    try:
        created = datetime.fromisoformat(record.created_at)
        age_days = (datetime.now() - created).total_seconds() / 86400.0
        # Decay half-life of 30 days -> lambda = ln(2) / 30 = 0.0231
        recency = math.exp(-0.0231 * max(0.0, age_days))
    except Exception:
        recency = 1.0

    # 3. Reference Decay
    factor = 1.0
    if record.last_referenced_at:
        try:
            last_ref = datetime.fromisoformat(record.last_referenced_at)
            ref_age = (datetime.now() - last_ref).total_seconds() / 86400.0
            if ref_age <= 1.0:
                factor = 1.0
            elif ref_age <= 30.0:
                factor = 0.8
            elif ref_age <= 90.0:
                factor = 0.5
            else:
                factor = 0.2
        except Exception:
            factor = 1.0
    
    references = math.log1p(record.reference_count) * factor

    # 4. Confidence Weight
    confidence = record.confidence * 2.0

    # 5. Lifecycle Penalty
    penalties = {
        "active": 0.0,
        "historical": -1.0,
        "superseded": -5.0,
        "archived": -10.0
    }
    lifecycle_penalty = penalties.get(record.lifecycle_status.lower(), 0.0)

    # 6. Total
    total = priority + recency + references + confidence + lifecycle_penalty

    return RetrievalScore(
        total=total,
        priority=priority,
        recency=recency,
        references=references,
        confidence=confidence,
        lifecycle_penalty=lifecycle_penalty,
    )
