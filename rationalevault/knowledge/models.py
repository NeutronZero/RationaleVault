"""RationaleVault Knowledge Models — Core data structures for synthesized knowledge.

Knowledge is derived state, never primary state. Every KnowledgeObject must
be traceable back to source memories and source events through its ProvenanceChain.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from rationalevault.knowledge.relation_types import RelationType


class KnowledgeType(str, Enum):
    """Types of knowledge that can be synthesized from memories."""
    ARCHITECTURE_PRINCIPLE = "ARCHITECTURE_PRINCIPLE"
    PROJECT_INVARIANT = "PROJECT_INVARIANT"
    LESSON = "LESSON"
    FAILURE_PATTERN = "FAILURE_PATTERN"
    WORKFLOW_PATTERN = "WORKFLOW_PATTERN"
    RESEARCH_FINDING = "RESEARCH_FINDING"
    DECISION_LINEAGE = "DECISION_LINEAGE"


class KnowledgeDomain(str, Enum):
    """Domain classification for knowledge retrieval and organization."""
    ARCHITECTURE = "ARCHITECTURE"
    PROCESS = "PROCESS"
    QUALITY = "QUALITY"
    RESEARCH = "RESEARCH"
    OPERATIONS = "OPERATIONS"


class KnowledgeLifecycle(str, Enum):
    """Lifecycle states for knowledge objects."""
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class KnowledgeTransferability(str, Enum):
    """Transferability — can this knowledge leave its project?"""
    LOCAL_ONLY = "LOCAL_ONLY"
    REUSABLE = "REUSABLE"
    ORGANIZATIONAL = "ORGANIZATIONAL"


def is_transferable(transferability: str) -> bool:
    """Check if a transferability value allows cross-project transfer."""
    return transferability in {
        KnowledgeTransferability.REUSABLE.value,
        KnowledgeTransferability.ORGANIZATIONAL.value,
    }


class EpistemicStatus(str, Enum):
    """Epistemic status — how confident are we that this knowledge is true.

    Orthogonal to KnowledgeLifecycle (freshness):
      ACTIVE + VALIDATED = current and confident
      ACTIVE + CONFLICTED = current but disputed
      SUPERSEDED + VALIDATED = was confident when active, now replaced

    Derived from evidence by KnowledgeProjection. Not stored in DB.
    """
    PROPOSED   = "PROPOSED"
    VALIDATED  = "VALIDATED"
    INVARIANT  = "INVARIANT"
    CONFLICTED = "CONFLICTED"
    TOMBSTONED = "TOMBSTONED"


def generate_knowledge_id(
    knowledge_type: str, title: str, content: str, project_id: str = "",
) -> str:
    """Deterministic ID generation for knowledge objects.

    Includes project_id to prevent cross-project ID collisions.
    """
    norm_content = " ".join(content.lower().strip().split())
    norm_title = " ".join(title.lower().strip().split())
    data = f"{knowledge_type.lower()}:{project_id}:{norm_title}:{norm_content}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass
class KnowledgeConfidence:
    """Derived confidence model — computed from evidence, not set manually.

    Follows the same explainability principle as RetrievalScore and MemoryCitation:
    everything must be explainable.
    """
    memory_count: int
    source_event_count: int
    contradiction_count: int
    average_memory_confidence: float
    score: float = 0.0

    def __post_init__(self) -> None:
        if self.memory_count == 0:
            self.score = 0.0
            return
        # Base score from memory confidence average
        base = self.average_memory_confidence
        # Boost from evidence count (diminishing returns)
        evidence_boost = min(0.2, self.memory_count * 0.05)
        # Penalty from contradictions
        contradiction_penalty = self.contradiction_count * 0.15
        self.score = max(0.0, min(1.0, base + evidence_boost - contradiction_penalty))

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_count": self.memory_count,
            "source_event_count": self.source_event_count,
            "contradiction_count": self.contradiction_count,
            "average_memory_confidence": self.average_memory_confidence,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeConfidence:
        return cls(
            memory_count=d.get("memory_count", 0),
            source_event_count=d.get("source_event_count", 0),
            contradiction_count=d.get("contradiction_count", 0),
            average_memory_confidence=d.get("average_memory_confidence", 0.0),
            score=d.get("score", 0.0),
        )


@dataclass
class ProvenanceChain:
    """Full traceability from knowledge back to source events.

    Every KnowledgeObject MUST have a ProvenanceChain. This is the core invariant:
    100% provenance required.
    """
    knowledge_id: str
    source_memory_ids: list[str]
    source_event_ids: list[str]
    synthesis_event_id: str
    confidence: KnowledgeConfidence
    evidence_count: int
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "source_memory_ids": self.source_memory_ids,
            "source_event_ids": self.source_event_ids,
            "synthesis_event_id": self.synthesis_event_id,
            "confidence": self.confidence.to_dict(),
            "evidence_count": self.evidence_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProvenanceChain:
        conf_data = d.get("confidence", {})
        if isinstance(conf_data, dict):
            confidence = KnowledgeConfidence.from_dict(conf_data)
        else:
            confidence = KnowledgeConfidence(0, 0, 0, 0.0, float(conf_data))

        return cls(
            knowledge_id=d.get("knowledge_id", ""),
            source_memory_ids=d.get("source_memory_ids", []),
            source_event_ids=d.get("source_event_ids", []),
            synthesis_event_id=d.get("synthesis_event_id", ""),
            confidence=confidence,
            evidence_count=d.get("evidence_count", 0),
            created_at=d.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class KnowledgeObject:
    """A synthesized knowledge artifact derived from memories.

    Knowledge is derived state, never primary state. All synthesis is
    traceable back to source memories and source events.
    """
    id: str
    version: int
    title: str
    content: str
    knowledge_type: KnowledgeType
    knowledge_domain: KnowledgeDomain
    confidence: KnowledgeConfidence
    importance: str
    provenance: ProvenanceChain
    tags: list[str] = field(default_factory=list)
    supporting_memory_ids: list[str] = field(default_factory=list)
    contradicting_memory_ids: list[str] = field(default_factory=list)
    lifecycle_status: str = KnowledgeLifecycle.ACTIVE.value
    superseded_by: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    project_id: str = ""
    transferability: str = KnowledgeTransferability.LOCAL_ONLY.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "content": self.content,
            "knowledge_type": self.knowledge_type.value,
            "knowledge_domain": self.knowledge_domain.value,
            "confidence": self.confidence.to_dict(),
            "importance": self.importance,
            "provenance": self.provenance.to_dict(),
            "tags": self.tags,
            "supporting_memory_ids": self.supporting_memory_ids,
            "contradicting_memory_ids": self.contradicting_memory_ids,
            "lifecycle_status": self.lifecycle_status,
            "superseded_by": self.superseded_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "project_id": self.project_id,
            "transferability": self.transferability,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeObject:
        conf_data = d.get("confidence", {})
        if isinstance(conf_data, dict):
            confidence = KnowledgeConfidence.from_dict(conf_data)
        else:
            confidence = KnowledgeConfidence(0, 0, 0, 0.0, float(conf_data))

        prov_data = d.get("provenance", {})
        provenance = ProvenanceChain.from_dict(prov_data) if prov_data else ProvenanceChain(
            knowledge_id=d.get("id", ""),
            source_memory_ids=[],
            source_event_ids=[],
            synthesis_event_id="",
            confidence=confidence,
            evidence_count=0,
        )

        return cls(
            id=d["id"],
            version=d.get("version", 1),
            title=d["title"],
            content=d["content"],
            knowledge_type=KnowledgeType(d["knowledge_type"]),
            knowledge_domain=KnowledgeDomain(d.get("knowledge_domain", KnowledgeDomain.ARCHITECTURE.value)),
            confidence=confidence,
            importance=d.get("importance", "medium"),
            provenance=provenance,
            tags=d.get("tags", []),
            supporting_memory_ids=d.get("supporting_memory_ids", []),
            contradicting_memory_ids=d.get("contradicting_memory_ids", []),
            lifecycle_status=d.get("lifecycle_status", KnowledgeLifecycle.ACTIVE.value),
            superseded_by=d.get("superseded_by"),
            created_at=d.get("created_at", datetime.now().isoformat()),
            updated_at=d.get("updated_at", datetime.now().isoformat()),
            project_id=d.get("project_id", ""),
            transferability=d.get("transferability", KnowledgeTransferability.LOCAL_ONLY.value),
        )


@dataclass
class ArchitecturePrinciple(KnowledgeObject):
    """Specialized knowledge for architecture decisions.

    Architecture knowledge is not equivalent to generic knowledge.
    These are project constitution-level decisions.
    """
    principle_strength: float = 0.0
    supporting_decisions: list[str] = field(default_factory=list)
    supporting_rationales: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "principle_strength": self.principle_strength,
            "supporting_decisions": self.supporting_decisions,
            "supporting_rationales": self.supporting_rationales,
        })
        return base

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ArchitecturePrinciple:
        base = KnowledgeObject.from_dict(d)
        return cls(
            id=base.id,
            version=base.version,
            title=base.title,
            content=base.content,
            knowledge_type=base.knowledge_type,
            knowledge_domain=base.knowledge_domain,
            confidence=base.confidence,
            importance=base.importance,
            provenance=base.provenance,
            tags=base.tags,
            supporting_memory_ids=base.supporting_memory_ids,
            contradicting_memory_ids=base.contradicting_memory_ids,
            lifecycle_status=base.lifecycle_status,
            superseded_by=base.superseded_by,
            created_at=base.created_at,
            updated_at=base.updated_at,
            project_id=base.project_id,
            transferability=base.transferability,
            principle_strength=d.get("principle_strength", 0.0),
            supporting_decisions=d.get("supporting_decisions", []),
            supporting_rationales=d.get("supporting_rationales", []),
        )


@dataclass
class ProjectInvariant(KnowledgeObject):
    """Project-level invariants that must always hold.

    These are not architecture decisions — they are fundamental truths
    about the project that never change.

    Examples from RationaleVault:
    - State is derived from events
    - Knowledge is derived state
    - 100% provenance required
    - No orphan memories
    """

    def __post_init__(self) -> None:
        self.knowledge_type = KnowledgeType.PROJECT_INVARIANT
        self.importance = "critical"
        self.transferability = KnowledgeTransferability.ORGANIZATIONAL.value


@dataclass
class KnowledgeRelation:
    """Relationships between knowledge objects."""
    source_id: str
    target_id: str
    relation_type: RelationType
    confidence: float
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self) -> None:
        if not isinstance(self.relation_type, RelationType):
            raise TypeError(
                f"relation_type must be a RelationType, got {type(self.relation_type).__name__}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KnowledgeRelation:
        rt = d["relation_type"]
        if isinstance(rt, str):
            rt = RelationType.from_str(rt)
        return cls(
            source_id=d["source_id"],
            target_id=d["target_id"],
            relation_type=rt,
            confidence=d.get("confidence", 1.0),
            created_at=d.get("created_at", datetime.now().isoformat()),
        )
