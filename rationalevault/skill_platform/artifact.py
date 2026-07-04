"""
RationaleVault Skill Platform — Artifact Contracts.

Defines the enums, value objects, and lineage tracing structures for durable
outputs produced during skill execution.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ArtifactKind(str, Enum):
    """Supported kinds of durable artifacts."""
    MARKDOWN = "MARKDOWN"
    JSON = "JSON"
    CODE_PATCH = "CODE_PATCH"
    DIFF = "DIFF"
    DIAGRAM = "DIAGRAM"
    REPORT = "REPORT"
    DATASET = "DATASET"
    OTHER = "OTHER"


@dataclass(frozen=True)
class ArtifactReference:
    """Represents the locator of a durable artifact independent of underlying storage."""
    scheme: str  # e.g., "file", "s3", "git"
    location: str  # e.g., "reports/run.md", "buckets/artifacts/result.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheme": self.scheme,
            "location": self.location,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ArtifactReference:
        return cls(
            scheme=d["scheme"],
            location=d["location"],
        )


@dataclass(frozen=True)
class Artifact:
    """
    Durable output promoted after successful execution evaluation.
    
    artifact_id is deterministic: ART-[hash] from (skill_id, execution_id, content_hash).
    """
    artifact_id: str
    kind: ArtifactKind
    reference: ArtifactReference
    hash: str
    size: int
    mime_type: str
    created_at: str

    @staticmethod
    def generate_artifact_id(skill_id: str, execution_id: str, content_hash: str) -> str:
        data = f"artifact:{skill_id}:{execution_id}:{content_hash}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"ART-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind.value,
            "reference": self.reference.to_dict(),
            "hash": self.hash,
            "size": self.size,
            "mime_type": self.mime_type,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Artifact:
        return cls(
            artifact_id=d["artifact_id"],
            kind=ArtifactKind(d["kind"]),
            reference=ArtifactReference.from_dict(d["reference"]),
            hash=d["hash"],
            size=d["size"],
            mime_type=d["mime_type"],
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class ArtifactCandidate:
    """An ephemeral artifact candidate proposed for promotion."""
    candidate_id: str  # ACAND-[hash]
    kind: ArtifactKind
    reference: ArtifactReference
    hash: str
    size: int
    mime_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def generate_candidate_id(skill_id: str, execution_id: str, content_hash: str) -> str:
        data = f"candidate_artifact:{skill_id}:{execution_id}:{content_hash}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"ACAND-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "kind": self.kind.value,
            "reference": self.reference.to_dict(),
            "hash": self.hash,
            "size": self.size,
            "mime_type": self.mime_type,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ArtifactCandidate:
        return cls(
            candidate_id=d["candidate_id"],
            kind=ArtifactKind(d["kind"]),
            reference=ArtifactReference.from_dict(d["reference"]),
            hash=d["hash"],
            size=d["size"],
            mime_type=d["mime_type"],
            metadata=d.get("metadata", {}),
        )


@dataclass(frozen=True)
class ArtifactLineage:
    """Traces the origin of a promoted Artifact through the entire cognitive/execution chain."""
    artifact_id: str
    result_id: str
    execution_id: str
    skill_id: str
    decision_id: str
    synthesis_id: str
    belief_id: str
    source_event_ids: list[str]
    projection_snapshot_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "result_id": self.result_id,
            "execution_id": self.execution_id,
            "skill_id": self.skill_id,
            "decision_id": self.decision_id,
            "synthesis_id": self.synthesis_id,
            "belief_id": self.belief_id,
            "source_event_ids": self.source_event_ids,
            "projection_snapshot_hash": self.projection_snapshot_hash,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ArtifactLineage:
        return cls(
            artifact_id=d["artifact_id"],
            result_id=d["result_id"],
            execution_id=d["execution_id"],
            skill_id=d["skill_id"],
            decision_id=d["decision_id"],
            synthesis_id=d["synthesis_id"],
            belief_id=d["belief_id"],
            source_event_ids=d.get("source_event_ids", []),
            projection_snapshot_hash=d["projection_snapshot_hash"],
        )
