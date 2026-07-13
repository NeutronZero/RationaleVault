"""CanonicalTimestamp — immutable value object for UTC timestamps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class CanonicalTimestamp:
    """Immutable UTC timestamp with RFC 3339 formatting."""

    value: datetime

    def __post_init__(self) -> None:
        """Enforce UTC and microsecond precision."""
        if self.value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")
        if self.value.tzinfo != timezone.utc:
            object.__setattr__(self, "value", self.value.astimezone(timezone.utc))

    def to_iso8601(self) -> str:
        """Return RFC 3339 formatted string: YYYY-MM-DDTHH:MM:SS.ffffffZ"""
        return self.value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def to_datetime(self) -> datetime:
        """Return the underlying datetime object."""
        return self.value

    def to_dict(self) -> str:
        """Return canonical string representation."""
        return self.to_iso8601()

    @classmethod
    def from_datetime(cls, dt: datetime) -> CanonicalTimestamp:
        """Create from datetime object."""
        return cls(value=dt)

    @classmethod
    def from_iso8601(cls, s: str) -> CanonicalTimestamp:
        """Create from ISO 8601 string."""
        if not s.endswith("Z"):
            raise ValueError(f"Timestamp must end with Z: {s}")
        dt = datetime.strptime(s[:-1], "%Y-%m-%dT%H:%M:%S.%f").replace(
            tzinfo=timezone.utc
        )
        return cls(value=dt)
