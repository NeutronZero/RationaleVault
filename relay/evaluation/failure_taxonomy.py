from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class FailureType(str, Enum):
    QUESTION_LOSS = "QUESTION_LOSS"
    TASK_LOSS = "TASK_LOSS"
    DECISION_LOSS = "DECISION_LOSS"
    TASK_HALLUCINATION = "TASK_HALLUCINATION"
    DECISION_HALLUCINATION = "DECISION_HALLUCINATION"
    BLOCKER_AMBIGUITY = "BLOCKER_AMBIGUITY"
    NEXT_ACTION_ERROR = "NEXT_ACTION_ERROR"
    CONTEXT_DRIFT = "CONTEXT_DRIFT"
    EXTRACTION_FALSE_POSITIVE = "EXTRACTION_FALSE_POSITIVE"
    EXTRACTION_LEAK = "EXTRACTION_LEAK"
    PROTOCOL_VIOLATION = "PROTOCOL_VIOLATION"
    BLOCKER_BYPASS = "BLOCKER_BYPASS"
    CONTEXT_COMPRESSION_FAILURE = "CONTEXT_COMPRESSION_FAILURE"
    DECISION_CONTRADICTION = "DECISION_CONTRADICTION"
    DECISION_MUTATION = "DECISION_MUTATION"


@dataclass
class FailureAttribution:
    failure_type: FailureType
    source_agent: str
    target_agent: str
    item_id: str
    expected: Optional[str] = None
    observed: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_type": self.failure_type.value,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "item_id": self.item_id,
            "expected": self.expected,
            "observed": self.observed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailureAttribution:
        return cls(
            failure_type=FailureType(data["failure_type"]),
            source_agent=data["source_agent"],
            target_agent=data["target_agent"],
            item_id=data["item_id"],
            expected=data.get("expected"),
            observed=data.get("observed"),
        )
