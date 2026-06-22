from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Observation:
    """
    Represents a raw factual statement or observation extracted from agent output.
    """
    text: str
    confidence: float = 1.0
    source_context: Optional[str] = None


@dataclass
class CandidateEvent:
    """
    Represents a suggested event before validation and human commit.
    """
    event_type: str
    stream_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    backing_observation: Optional[str] = None
