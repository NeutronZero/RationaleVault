from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

class ProjectionKind(str, Enum):
    BASE = "base"
    DERIVED = "derived"
    COMPOSITE = "composite"

@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, version_str: str) -> SemVer:
        parts = version_str.strip().split('.')
        if len(parts) != 3:
            raise ValueError(f"Invalid semver string: {version_str}")
        try:
            return cls(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            raise ValueError(f"Invalid semver digits in: {version_str}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

class BaseProjection:
    """Base class for all deterministic projections in RationaleVault."""
    projection_name: ClassVar[str]
    version: ClassVar[SemVer]
    projection_kind: ClassVar[ProjectionKind]
    dependencies: ClassVar[list[type[BaseProjection]]] = []
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 100
