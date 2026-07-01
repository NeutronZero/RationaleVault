"""RationaleVault Organization Activity Projection — Pure temporal observation layer.

Temporal Signals → OrganizationActivityState

Observable facts only. No recommendations, no prioritization, no next actions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, ClassVar
from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer

from rationalevault.organization.models import OrganizationState, KnowledgeLineage, CrossProjectConflict
from rationalevault.organization.projection import OrganizationProjection
from rationalevault.organization.utils import resolve_compiled_at


@dataclass
class ProjectActivity:
    """Per-project activity observation. Temporal data only, no interpretation."""
    project_id: str
    recent_event_count: int = 0
    last_event_at: str = ""
    recent_knowledge_count: int = 0
    recent_memory_count: int = 0


@dataclass
class OrgTransferEvent:
    """A knowledge transfer observed within the activity window."""
    knowledge_id: str
    knowledge_title: str
    source_project: str
    target_project: str
    created_at: str


@dataclass
class OrgConflictEvent:
    """A cross-project conflict observed within the activity window."""
    conflict_id: str
    project_a: str
    project_b: str
    detected_at: str


@dataclass
class KnowledgeSummary:
    """Summary of a knowledge object for activity reporting."""
    knowledge_id: str
    title: str
    project_id: str
    knowledge_type: str
    created_at: str


@dataclass
class OrganizationActivityState:
    """Pure temporal observation of organizational activity.

    No recommendations. No prioritization. No next actions.
    Only observable facts derived from EventRecord.recorded_at,
    KnowledgeObject.created_at/updated_at, and MemoryRecord.created_at.
    """
    compiled_at: str
    projection_version: str = "1.0"
    activity_window_hours: int = 72
    project_count: int = 0
    active_projects: list[ProjectActivity] = field(default_factory=list)
    inactive_projects: list[str] = field(default_factory=list)
    recent_transfers: list[OrgTransferEvent] = field(default_factory=list)
    recent_conflicts: list[OrgConflictEvent] = field(default_factory=list)
    recent_knowledge: list[KnowledgeSummary] = field(default_factory=list)
    overall_activity_level: float = 0.0

    MAX_SUMMARY_ITEMS: int = 10

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiled_at": self.compiled_at,
            "projection_version": self.projection_version,
            "activity_window_hours": self.activity_window_hours,
            "project_count": self.project_count,
            "active_projects": [
                {
                    "project_id": p.project_id,
                    "recent_event_count": p.recent_event_count,
                    "last_event_at": p.last_event_at,
                    "recent_knowledge_count": p.recent_knowledge_count,
                    "recent_memory_count": p.recent_memory_count,
                }
                for p in self.active_projects
            ],
            "inactive_projects": sorted(self.inactive_projects),
            "recent_transfers": [
                {
                    "knowledge_id": t.knowledge_id,
                    "knowledge_title": t.knowledge_title,
                    "source_project": t.source_project,
                    "target_project": t.target_project,
                    "created_at": t.created_at,
                }
                for t in self.recent_transfers
            ],
            "recent_conflicts": [
                {
                    "conflict_id": c.conflict_id,
                    "project_a": c.project_a,
                    "project_b": c.project_b,
                    "detected_at": c.detected_at,
                }
                for c in self.recent_conflicts
            ],
            "recent_knowledge": [
                {
                    "knowledge_id": k.knowledge_id,
                    "title": k.title,
                    "project_id": k.project_id,
                    "knowledge_type": k.knowledge_type,
                    "created_at": k.created_at,
                }
                for k in self.recent_knowledge
            ],
            "overall_activity_level": round(self.overall_activity_level, 4),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OrganizationActivityState:
        return cls(
            compiled_at=d["compiled_at"],
            projection_version=d.get("projection_version", "1.0"),
            activity_window_hours=d.get("activity_window_hours", 72),
            project_count=d.get("project_count", 0),
            active_projects=[
                ProjectActivity(
                    project_id=p["project_id"],
                    recent_event_count=p["recent_event_count"],
                    last_event_at=p["last_event_at"],
                    recent_knowledge_count=p.get("recent_knowledge_count", 0),
                    recent_memory_count=p.get("recent_memory_count", 0),
                )
                for p in d.get("active_projects", [])
            ],
            inactive_projects=d.get("inactive_projects", []),
            recent_transfers=[
                OrgTransferEvent(
                    knowledge_id=t["knowledge_id"],
                    knowledge_title=t["knowledge_title"],
                    source_project=t["source_project"],
                    target_project=t["target_project"],
                    created_at=t["created_at"],
                )
                for t in d.get("recent_transfers", [])
            ],
            recent_conflicts=[
                OrgConflictEvent(
                    conflict_id=c["conflict_id"],
                    project_a=c["project_a"],
                    project_b=c["project_b"],
                    detected_at=c["detected_at"],
                )
                for c in d.get("recent_conflicts", [])
            ],
            recent_knowledge=[
                KnowledgeSummary(
                    knowledge_id=k["knowledge_id"],
                    title=k["title"],
                    project_id=k["project_id"],
                    knowledge_type=k["knowledge_type"],
                    created_at=k["created_at"],
                )
                for k in d.get("recent_knowledge", [])
            ],
            overall_activity_level=d.get("overall_activity_level", 0.0),
        )


class OrganizationActivityProjection(BaseProjection):
    """Projects temporal signals into activity observations.

    Pure observation layer. No interpretation. No recommendations.
    """
    projection_name: ClassVar[str] = "OrganizationActivity"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
    dependencies: ClassVar[list[type[BaseProjection]]] = [OrganizationProjection]
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 70

    @staticmethod
    def project(
        project_ids: list[str],
        recent_events_by_project: dict[str, list],
        recent_knowledge_by_project: dict[str, list],
        recent_memories_by_project: dict[str, list],
        org_state: OrganizationState,
        activity_window_hours: int = 72,
        reference_time: datetime | None = None,
    ) -> OrganizationActivityState:
        """Build activity state from temporal signals.

        Args:
            project_ids: All registered project IDs.
            recent_events_by_project: Per-project events within window.
            recent_knowledge_by_project: Per-project knowledge objects within window.
            recent_memories_by_project: Per-project memories within window.
            org_state: Current OrganizationState for lineage/conflict data.
            activity_window_hours: How far back to consider "recent".
            reference_time: Optional reference time to run projection deterministically.

        Returns:
            OrganizationActivityState with observable facts only.
        """
        active_projects, inactive_projects = OrganizationActivityProjection._build_project_activity(
            project_ids, recent_events_by_project, recent_knowledge_by_project,
            recent_memories_by_project,
        )
        recent_transfers = OrganizationActivityProjection._detect_recent_transfers(
            org_state, recent_knowledge_by_project,
        )
        recent_conflicts = OrganizationActivityProjection._detect_recent_conflicts(
            org_state, recent_knowledge_by_project,
        )
        recent_knowledge = OrganizationActivityProjection._build_recent_knowledge(
            recent_knowledge_by_project,
        )
        overall_activity_level = (
            len(active_projects) / len(project_ids)
            if project_ids else 0.0
        )

        return OrganizationActivityState(
            compiled_at=resolve_compiled_at(reference_time),
            activity_window_hours=activity_window_hours,
            project_count=len(project_ids),
            active_projects=active_projects,
            inactive_projects=sorted(inactive_projects),
            recent_transfers=recent_transfers,
            recent_conflicts=recent_conflicts,
            recent_knowledge=recent_knowledge,
            overall_activity_level=overall_activity_level,
        )

    @staticmethod
    def _build_project_activity(
        project_ids: list[str],
        recent_events_by_project: dict[str, list],
        recent_knowledge_by_project: dict[str, list],
        recent_memories_by_project: dict[str, list],
    ) -> tuple[list[ProjectActivity], list[str]]:
        """Build per-project activity. Temporal data only."""
        active: list[ProjectActivity] = []
        inactive: list[str] = []

        for pid in project_ids:
            events = recent_events_by_project.get(pid, [])
            knowledge = recent_knowledge_by_project.get(pid, [])
            memories = recent_memories_by_project.get(pid, [])

            event_count = len(events)
            knowledge_count = len(knowledge)
            memory_count = len(memories)

            last_event_at = ""
            if events:
                try:
                    timestamps = [
                        e.recorded_at.isoformat() if hasattr(e, "recorded_at") and e.recorded_at
                        else str(getattr(e, "created_at", ""))
                        for e in events
                        if getattr(e, "recorded_at", None) or getattr(e, "created_at", None)
                    ]
                    if timestamps:
                        last_event_at = sorted(timestamps, reverse=True)[0]
                except Exception:
                    last_event_at = ""

            pa = ProjectActivity(
                project_id=pid,
                recent_event_count=event_count,
                last_event_at=last_event_at,
                recent_knowledge_count=knowledge_count,
                recent_memory_count=memory_count,
            )

            # Deterministic inactivity: all counts must be zero
            if event_count == 0 and knowledge_count == 0 and memory_count == 0:
                inactive.append(pid)
            else:
                active.append(pa)

        # Sort active by event_count descending, then project_id ascending (tiebreaker)
        active.sort(key=lambda p: (-p.recent_event_count, p.project_id))
        inactive.sort()

        return active, inactive

    @staticmethod
    def _detect_recent_transfers(
        org_state: OrganizationState,
        recent_knowledge_by_project: dict[str, list],
    ) -> list[OrgTransferEvent]:
        """Detect transfers where target project has recent knowledge."""
        transfers: list[OrgTransferEvent] = []

        # Pre-build lookup mapping (project_id, knowledge_id) -> knowledge object
        recent_knowledge_map = {}
        for pid, klist in recent_knowledge_by_project.items():
            for k in klist:
                k_id = str(getattr(k, "id", ""))
                recent_knowledge_map[(pid, k_id)] = k

        for kid, lineage in org_state.active_lineages.items():
            for target_pid in lineage.current_projects:
                if target_pid == lineage.origin_project:
                    continue
                k = recent_knowledge_map.get((target_pid, kid))
                if k is not None:
                    created_at = getattr(k, "created_at", "")
                    transfers.append(OrgTransferEvent(
                        knowledge_id=kid,
                        knowledge_title=getattr(k, "title", ""),
                        source_project=lineage.origin_project,
                        target_project=target_pid,
                        created_at=created_at or "",
                    ))

        # Deterministic ordering: newest first, then knowledge_id ascending
        transfers.sort(key=lambda t: (-OrganizationActivityProjection._parse_time(t.created_at), t.knowledge_id))
        return transfers

    @staticmethod
    def _detect_recent_conflicts(
        org_state: OrganizationState,
        recent_knowledge_by_project: dict[str, list],
    ) -> list[OrgConflictEvent]:
        """Detect conflicts involving knowledge that was recently updated."""
        # Pre-build lookup mapping of knowledge_id -> timestamp and verify existence in recent_knowledge_ids
        recent_knowledge_ids: set[str] = set()
        recent_knowledge_timestamps: dict[str, str] = {}
        for pid, klist in recent_knowledge_by_project.items():
            for k in klist:
                kid = str(getattr(k, "id", ""))
                recent_knowledge_ids.add(kid)
                timestamp = getattr(k, "updated_at", "") or getattr(k, "created_at", "") or ""
                if timestamp:
                    if kid not in recent_knowledge_timestamps or timestamp > recent_knowledge_timestamps[kid]:
                        recent_knowledge_timestamps[kid] = timestamp

        conflicts: list[OrgConflictEvent] = []
        for conflict in org_state.cross_project_conflicts:
            if (conflict.knowledge_a_id in recent_knowledge_ids
                    or conflict.knowledge_b_id in recent_knowledge_ids):
                detected_at = ""
                if conflict.knowledge_a_id in recent_knowledge_timestamps:
                    detected_at = recent_knowledge_timestamps[conflict.knowledge_a_id]
                elif conflict.knowledge_b_id in recent_knowledge_timestamps:
                    detected_at = recent_knowledge_timestamps[conflict.knowledge_b_id]

                conflicts.append(OrgConflictEvent(
                    conflict_id=conflict.conflict_id,
                    project_a=conflict.project_a,
                    project_b=conflict.project_b,
                    detected_at=detected_at,
                ))

        # Deterministic ordering
        conflicts.sort(key=lambda c: (-OrganizationActivityProjection._parse_time(c.detected_at), c.conflict_id))
        return conflicts

    @staticmethod
    def _build_recent_knowledge(
        recent_knowledge_by_project: dict[str, list],
    ) -> list[KnowledgeSummary]:
        """Build summary list of recently created/updated knowledge."""
        summaries: list[KnowledgeSummary] = []
        for pid, klist in recent_knowledge_by_project.items():
            for k in klist:
                summaries.append(KnowledgeSummary(
                    knowledge_id=str(getattr(k, "id", "")),
                    title=getattr(k, "title", ""),
                    project_id=pid,
                    knowledge_type=str(getattr(k, "knowledge_type", "")),
                    created_at=getattr(k, "created_at", "") or "",
                ))
        # Deterministic ordering: newest first, then knowledge_id ascending
        summaries.sort(key=lambda s: (-OrganizationActivityProjection._parse_time(s.created_at), s.knowledge_id))
        return summaries[:OrganizationActivityState.MAX_SUMMARY_ITEMS]

    @staticmethod
    def _parse_time(timestamp: str) -> float:
        """Parse ISO timestamp to epoch for deterministic sorting. Returns 0.0 on failure."""
        if not timestamp:
            return 0.0
        try:
            dt = datetime.fromisoformat(timestamp)
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0.0
