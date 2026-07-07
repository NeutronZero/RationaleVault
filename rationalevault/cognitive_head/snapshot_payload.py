"""
RationaleVault Snapshot Payload — Typed serialization for projection snapshots.

Base class: ProjectionSnapshotPayload
  - Common fields: sequence, schema_version, projection_version, snapshot_hash
  - Future projections (knowledge, organization) extend this base

Concrete class: CognitiveHeadSnapshotPayload
  - Stores serialized CognitiveHead state (tasks, decisions, questions, etc.)
  - Converts to/from CognitiveHead via to_cognitive_head() / from_cognitive_head()

Design rules:
  - No dict[str, Any] payloads. Every field is typed.
  - Hash is computed from the payload dict (excluding snapshot_hash itself).
  - Snapshots are immutable after creation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any, ClassVar, Optional
from uuid import UUID

from rationalevault.cognitive_head.compiler import CognitiveHead
from rationalevault.cognitive_head.reducers import (
    DecisionState,
    QuestionState,
    TaskState,
)


def _compute_hash(data: dict[str, Any]) -> str:
    """Compute SHA-256 hash of a payload dict for integrity validation."""
    canonical = json.dumps(data, sort_keys=True, default=str).encode()
    return hashlib.sha256(canonical).hexdigest()


@dataclass
class ProjectionSnapshotPayload:
    """
    Base class for all projection snapshot payloads.

    Attributes:
        sequence:           Event sequence number of the last event included.
        schema_version:     Schema version for forward compatibility.
        projection_version: Projection-specific version for evolution.
        snapshot_hash:      SHA-256 hash of the payload (excluding this field).

    Class attributes (override in subclasses):
        SCHEMA_VERSION:     Current schema version for this projection type.
        PROJECTION_VERSION: Current projection version for this type.
    """
    SCHEMA_VERSION: ClassVar[int] = 1
    PROJECTION_VERSION: ClassVar[int] = 1

    sequence: int
    schema_version: int = field(default=1)
    projection_version: int = field(default=1)
    snapshot_hash: str = ""

    def to_dict(self, exclude_hash: bool = False) -> dict[str, Any]:
        """Serialize to a plain dict. Subclasses override to add fields."""
        d: dict[str, Any] = {
            "sequence": self.sequence,
            "schema_version": self.schema_version,
            "projection_version": self.projection_version,
        }
        if not exclude_hash:
            d["snapshot_hash"] = self.snapshot_hash
        return d

    def compute_hash(self) -> str:
        """Compute and return the hash of the payload (excluding snapshot_hash)."""
        return _compute_hash(self.to_dict(exclude_hash=True))

    def validate_hash(self) -> bool:
        """Verify the stored hash matches the computed hash."""
        return self.snapshot_hash == self.compute_hash()

    def with_hash(self) -> ProjectionSnapshotPayload:
        """Return a new payload with the hash field populated. Original is unchanged."""
        return replace(self, snapshot_hash=self.compute_hash())


@dataclass
class CognitiveHeadSnapshotPayload(ProjectionSnapshotPayload):
    """
    Typed snapshot payload for the CognitiveHead projection.

    Stores the serialized state of a compiled CognitiveHead, enabling
    delta replay without full event stream processing.

    Fields mirror CognitiveHead but use only primitive/serializable types.
    """
    SCHEMA_VERSION: ClassVar[int] = 1
    PROJECTION_VERSION: ClassVar[int] = 1

    project_id: str = ""
    project_name: str = ""
    project_goal: str = ""
    current_focus: str = ""
    ledger_version: int = 0
    compiled_at: str = ""

    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    decisions: dict[str, dict[str, Any]] = field(default_factory=dict)
    questions: dict[str, dict[str, Any]] = field(default_factory=dict)
    blockers: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, exclude_hash: bool = False) -> dict[str, Any]:
        """Serialize to a plain dict for JSON storage."""
        base = super().to_dict(exclude_hash=exclude_hash)
        base.update({
            "project_id": self.project_id,
            "project_name": self.project_name,
            "project_goal": self.project_goal,
            "current_focus": self.current_focus,
            "ledger_version": self.ledger_version,
            "compiled_at": self.compiled_at,
            "tasks": self.tasks,
            "decisions": self.decisions,
            "questions": self.questions,
            "blockers": self.blockers,
        })
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CognitiveHeadSnapshotPayload:
        """Deserialize from a plain dict."""
        return cls(
            sequence=data.get("sequence", 0),
            schema_version=data.get("schema_version", 1),
            projection_version=data.get("projection_version", 1),
            snapshot_hash=data.get("snapshot_hash", ""),
            project_id=data.get("project_id", ""),
            project_name=data.get("project_name", ""),
            project_goal=data.get("project_goal", ""),
            current_focus=data.get("current_focus", ""),
            ledger_version=data.get("ledger_version", 0),
            compiled_at=data.get("compiled_at", ""),
            tasks=data.get("tasks", {}),
            decisions=data.get("decisions", {}),
            questions=data.get("questions", {}),
            blockers=data.get("blockers", []),
        )

    @classmethod
    def from_cognitive_head(
        cls,
        head: CognitiveHead,
        sequence: int,
        all_tasks: Optional[dict[str, dict[str, Any]]] = None,
        all_decisions: Optional[dict[str, dict[str, Any]]] = None,
        all_questions: Optional[dict[str, dict[str, Any]]] = None,
    ) -> CognitiveHeadSnapshotPayload:
        """Create a snapshot payload from a compiled CognitiveHead.

        If all_tasks/all_decisions/all_questions are provided, they contain
        the full reducer state (including completed/superseded items) for
        delta replay. If None, only active items are stored (fast-path only).
        """
        tasks_dict = all_tasks if all_tasks is not None else {}
        if all_tasks is None:
            for t in head.active_tasks:
                tasks_dict[t.task_id] = {
                    "task_id": t.task_id,
                    "title": t.title,
                    "description": t.description,
                    "status": t.status,
                    "assignee": t.assignee,
                    "priority": t.priority,
                    "tags": t.tags,
                    "blocked_by": t.blocked_by,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                    "completed_at": t.completed_at,
                    "created_by": t.created_by,
                    "progress_notes": t.progress_notes,
                    "related_knowledge_ids": t.related_knowledge_ids,
                }

        decisions_dict = all_decisions if all_decisions is not None else {}
        if all_decisions is None:
            for d in head.active_decisions:
                decisions_dict[d.decision_id] = {
                    "decision_id": d.decision_id,
                    "title": d.title,
                    "description": d.description,
                    "status": d.status,
                    "rationale": d.rationale,
                    "context": d.context,
                    "category": d.category,
                    "superseded_by": d.superseded_by,
                    "created_at": d.created_at,
                    "accepted_at": d.accepted_at,
                    "created_by": d.created_by,
                }

        questions_dict = all_questions if all_questions is not None else {}
        if all_questions is None:
            for q in head.open_questions:
                questions_dict[q.question_id] = {
                    "question_id": q.question_id,
                    "title": q.title,
                    "description": q.description,
                    "status": q.status,
                    "priority": q.priority,
                    "resolution": q.resolution,
                    "blocks_task_ids": q.blocks_task_ids,
                    "raised_at": q.raised_at,
                    "resolved_at": q.resolved_at,
                    "raised_by": q.raised_by,
                }

        payload = cls(
            sequence=sequence,
            schema_version=cls.SCHEMA_VERSION,
            projection_version=cls.PROJECTION_VERSION,
            project_id=str(head.project_id),
            project_name=head.project_name,
            project_goal=head.project_goal,
            current_focus=head.current_focus,
            ledger_version=head.ledger_version,
            compiled_at=head.compiled_at,
            tasks=tasks_dict,
            decisions=decisions_dict,
            questions=questions_dict,
            blockers=head.blockers,
        )
        return payload.with_hash()

    def to_cognitive_head(self) -> CognitiveHead:
        """Reconstruct a CognitiveHead from this snapshot payload."""
        tasks = []
        for task_data in self.tasks.values():
            tasks.append(TaskState(
                task_id=task_data["task_id"],
                title=task_data["title"],
                description=task_data.get("description", ""),
                status=task_data.get("status", "open"),
                assignee=task_data.get("assignee"),
                priority=task_data.get("priority", "normal"),
                tags=task_data.get("tags", []),
                blocked_by=task_data.get("blocked_by", []),
                created_at=task_data.get("created_at"),
                updated_at=task_data.get("updated_at"),
                completed_at=task_data.get("completed_at"),
                created_by=task_data.get("created_by", ""),
                progress_notes=task_data.get("progress_notes", []),
                related_knowledge_ids=task_data.get(
                    "related_knowledge_ids", []
                ),
            ))

        decisions = []
        for d_data in self.decisions.values():
            decisions.append(DecisionState(
                decision_id=d_data["decision_id"],
                title=d_data["title"],
                description=d_data.get("description", ""),
                status=d_data.get("status", "proposed"),
                rationale=d_data.get("rationale", ""),
                context=d_data.get("context", ""),
                category=d_data.get("category", "general"),
                superseded_by=d_data.get("superseded_by"),
                created_at=d_data.get("created_at"),
                accepted_at=d_data.get("accepted_at"),
                created_by=d_data.get("created_by", ""),
            ))

        questions = []
        for q_data in self.questions.values():
            questions.append(QuestionState(
                question_id=q_data["question_id"],
                title=q_data["title"],
                description=q_data.get("description", ""),
                status=q_data.get("status", "open"),
                priority=q_data.get("priority", "normal"),
                resolution=q_data.get("resolution"),
                blocks_task_ids=q_data.get("blocks_task_ids", []),
                raised_at=q_data.get("raised_at"),
                resolved_at=q_data.get("resolved_at"),
                raised_by=q_data.get("raised_by", ""),
            ))

        return CognitiveHead(
            project_id=(
                UUID(self.project_id) if self.project_id else UUID(int=0)
            ),
            project_name=self.project_name,
            project_goal=self.project_goal,
            current_focus=self.current_focus,
            ledger_version=self.ledger_version,
            compiled_at=self.compiled_at,
            active_tasks=tasks,
            active_decisions=decisions,
            open_questions=questions,
            blockers=self.blockers,
        )
