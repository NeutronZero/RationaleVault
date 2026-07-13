"""CanonicalEnvelope — three-layer event structure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType


@dataclass(frozen=True, slots=True)
class CanonicalEnvelope:
    """Immutable canonical event envelope."""

    rvcj_version: int
    event_schema_version: int
    experience_id: str
    event_type: EventType
    stream_id: str
    sequence: int
    timestamp: CanonicalTimestamp
    actor: str
    payload: CanonicalPayload
    correlation_id: str | None = None
    causation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (for serialization)."""
        d: dict[str, Any] = {
            "rvcj_version": self.rvcj_version,
            "event_schema_version": self.event_schema_version,
            "experience_id": self.experience_id,
            "event_type": self.event_type.value,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp.to_dict(),
            "actor": self.actor,
            "payload": self.payload.to_dict(),
        }
        if self.correlation_id is not None:
            d["correlation_id"] = self.correlation_id
        if self.causation_id is not None:
            d["causation_id"] = self.causation_id
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonicalEnvelope:
        """Create from dictionary."""
        return cls(
            rvcj_version=data["rvcj_version"],
            event_schema_version=data["event_schema_version"],
            experience_id=data["experience_id"],
            event_type=EventType(data["event_type"]),
            stream_id=data["stream_id"],
            sequence=data["sequence"],
            timestamp=CanonicalTimestamp.from_iso8601(data["timestamp"]),
            actor=data["actor"],
            payload=CanonicalPayload.from_dict(data["payload"]),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
        )
