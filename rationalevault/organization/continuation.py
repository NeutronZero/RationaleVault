"""RationaleVault Organization Continuation Projection — Interpretation layer.

OrganizationState + OrganizationGraphState + OrganizationActivityState
    ↓
OrganizationContinuationState

Interpretation only. Not temporal observation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar
from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer

from rationalevault.organization.activity import OrganizationActivityState, OrganizationActivityProjection
from rationalevault.organization.graph import OrganizationGraphState, OrganizationGraphProjection
from rationalevault.organization.models import OrganizationState
from rationalevault.organization.utils import resolve_compiled_at
from rationalevault.organization.projection import OrganizationProjection


@dataclass
class OrganizationContinuationHealth:
    """Health metrics for organizational continuation."""
    activity_coverage: float = 0.0
    continuity: float = 0.0
    attention_accuracy: float = 0.0
    overall: float = 0.0


@dataclass
class OrganizationContinuationState:
    """Interpretation of organizational activity for continuation.

    Contains attention scoring, next actions, and summary.
    All derived from ActivityState + GraphState + OrganizationState.
    """
    compiled_at: str
    projection_version: str = "1.0"
    activity_compiled_at: str = ""

    projects_needing_attention: list[str] = field(default_factory=list)
    organizational_next_actions: list[str] = field(default_factory=list)
    continuation_summary: list[str] = field(default_factory=list)

    health: OrganizationContinuationHealth = field(default_factory=OrganizationContinuationHealth)

    MAX_SUMMARY_ITEMS: int = 10

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiled_at": self.compiled_at,
            "projection_version": self.projection_version,
            "activity_compiled_at": self.activity_compiled_at,
            "projects_needing_attention": self.projects_needing_attention,
            "organizational_next_actions": self.organizational_next_actions,
            "continuation_summary": self.continuation_summary[:self.MAX_SUMMARY_ITEMS],
            "health": {
                "activity_coverage": round(self.health.activity_coverage, 4),
                "continuity": round(self.health.continuity, 4),
                "attention_accuracy": round(self.health.attention_accuracy, 4),
                "overall": round(self.health.overall, 4),
            },
        }


class OrganizationContinuationProjection(BaseProjection):
    """Projects organizational continuation from activity + graph + org state.

    Interpretation layer. All outputs derived from existing projections.
    """
    projection_name: ClassVar[str] = "OrganizationContinuation"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
    dependencies: ClassVar[list[type[BaseProjection]]] = [
        OrganizationProjection,
        OrganizationGraphProjection,
        OrganizationActivityProjection,
    ]
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 80

    @staticmethod
    def project(
        org_state: OrganizationState,
        graph_state: OrganizationGraphState,
        activity_state: OrganizationActivityState,
        reference_time: datetime | None = None,
    ) -> OrganizationContinuationState:
        """Build continuation state from activity, graph, and organization data.

        Args:
            org_state: Current OrganizationState for structural data.
            graph_state: Current OrganizationGraphState for flow/hotspot data.
            activity_state: Current OrganizationActivityState for temporal data.
            reference_time: Optional reference time to run projection deterministically.

        Returns:
            OrganizationContinuationState with attention, actions, summary.
        """
        attention = OrganizationContinuationProjection._compute_projects_needing_attention(
            activity_state, graph_state, org_state,
        )
        next_actions = OrganizationContinuationProjection._compute_organizational_next_actions(
            activity_state, graph_state, attention,
        )
        summary = OrganizationContinuationProjection._build_continuation_summary(
            activity_state, attention, next_actions,
        )
        health = OrganizationContinuationProjection._compute_health(
            activity_state, attention,
        )

        return OrganizationContinuationState(
            compiled_at=resolve_compiled_at(reference_time),
            activity_compiled_at=activity_state.compiled_at,
            projects_needing_attention=attention,
            organizational_next_actions=next_actions,
            continuation_summary=summary,
            health=health,
        )

    @staticmethod
    def _compute_projects_needing_attention(
        activity_state: OrganizationActivityState,
        graph_state: OrganizationGraphState,
        org_state: OrganizationState,
    ) -> list[str]:
        """Binary attention scoring. No scores stored.

        A project needs attention if it is:
        - inactive (zero activity in window)
        - a contradiction hotspot (has conflict edges)
        - an extreme consumer (negative flow balance)
        """
        needing_attention: set[str] = set()

        # Inactive projects
        needing_attention.update(activity_state.inactive_projects)

        # Contradiction hotspots
        for pid, _ in graph_state.contradiction_hotspots:
            needing_attention.add(pid)

        # Extreme consumers (negative flow balance)
        for pid, balance in graph_state.knowledge_flow_balance.items():
            if balance < 0:
                needing_attention.add(pid)

        return sorted(needing_attention)

    @staticmethod
    def _compute_organizational_next_actions(
        activity_state: OrganizationActivityState,
        graph_state: OrganizationGraphState,
        projects_needing_attention: list[str],
    ) -> list[str]:
        """Priority-ordered organizational next actions.

        1. Resolve contradiction hotspots
        2. Follow up on recent transfers
        3. Address inactive projects
        4. Support extreme consumers
        5. Improve cluster cohesion
        6. Fallback: review knowledge health
        """
        actions: list[str] = []

        # 1. Resolve contradiction hotspots
        for pid, score in graph_state.contradiction_hotspots:
            actions.append(f"Resolve {int(score)} contradiction(s) involving project '{pid}'")

        # 2. Follow up on recent transfers
        seen_transfer_targets: set[str] = set()
        for transfer in activity_state.recent_transfers:
            if transfer.target_project not in seen_transfer_targets:
                seen_transfer_targets.add(transfer.target_project)
                actions.append(
                    f"Follow up on transferred knowledge to '{transfer.target_project}' "
                    f"from '{transfer.source_project}'"
                )

        # 3. Address inactive projects
        for pid in activity_state.inactive_projects:
            actions.append(f"Review inactive project '{pid}' — no activity in {activity_state.activity_window_hours}h")

        # 4. Support extreme consumers
        consumer_actions: list[tuple[str, int]] = []
        for pid, balance in graph_state.knowledge_flow_balance.items():
            if balance < 0:
                consumer_actions.append((pid, abs(balance)))
        consumer_actions.sort(key=lambda x: -x[1])
        for pid, magnitude in consumer_actions[:3]:
            actions.append(f"Support knowledge consumer '{pid}' (flow balance: -{magnitude})")

        # 5. Improve cluster cohesion
        if graph_state.health.cluster_cohesion < 0.5:
            actions.append(
                f"Improve organizational cluster cohesion (current: {graph_state.health.cluster_cohesion:.2f})"
            )

        # 6. Fallback
        if not actions:
            actions.append("Review organizational knowledge health — no urgent issues detected")

        return actions

    @staticmethod
    def _build_continuation_summary(
        activity_state: OrganizationActivityState,
        projects_needing_attention: list[str],
        next_actions: list[str],
    ) -> list[str]:
        """Build human-readable continuation summary. Bounded to MAX_SUMMARY_ITEMS."""
        summary: list[str] = []

        active_count = len(activity_state.active_projects)
        total = activity_state.project_count
        summary.append(
            f"{active_count} of {total} projects active in last {activity_state.activity_window_hours}h"
        )

        if activity_state.recent_transfers:
            summary.append(f"{len(activity_state.recent_transfers)} transfer(s) detected")

        if activity_state.recent_conflicts:
            summary.append(f"{len(activity_state.recent_conflicts)} conflict(s) detected")

        if activity_state.recent_knowledge:
            summary.append(f"{len(activity_state.recent_knowledge)} knowledge item(s) recently created/updated")

        if projects_needing_attention:
            summary.append(f"{len(projects_needing_attention)} project(s) need attention")

        if next_actions:
            summary.append(f"{len(next_actions)} recommended action(s)")

        if not activity_state.recent_transfers and not activity_state.recent_conflicts:
            summary.append("No significant organizational changes detected")

        # Bound
        return summary[:OrganizationContinuationState.MAX_SUMMARY_ITEMS]

    @staticmethod
    def _compute_health(
        activity_state: OrganizationActivityState,
        projects_needing_attention: list[str],
    ) -> OrganizationContinuationHealth:
        """Compute health metrics for continuation state."""
        total = activity_state.project_count
        active_count = len(activity_state.active_projects)

        # Activity coverage: % of projects with any activity
        activity_coverage = active_count / total if total > 0 else 1.0

        # Continuity: 1.0 - (attention / total)
        continuity = 1.0 - (len(projects_needing_attention) / total) if total > 0 else 1.0

        # Attention accuracy: placeholder — evaluator computes this precisely
        attention_accuracy = 1.0 if not projects_needing_attention else 0.7

        # Overall: geometric mean of non-zero metrics
        metrics = [activity_coverage, continuity, attention_accuracy]
        non_zero = [m for m in metrics if m > 0]
        if non_zero:
            product = 1.0
            for m in non_zero:
                product *= m
            overall = product ** (1.0 / len(non_zero))
        else:
            overall = 0.0

        return OrganizationContinuationHealth(
            activity_coverage=activity_coverage,
            continuity=continuity,
            attention_accuracy=attention_accuracy,
            overall=overall,
        )
