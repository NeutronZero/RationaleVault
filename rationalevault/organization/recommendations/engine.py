"""RationaleVault Recommendation Engine — Deterministic decision synthesis.

Consumes OrganizationState + OrganizationGraphState + OrganizationActivityState
+ OrganizationContinuationState to produce RecommendationSet.

No persistence. No new source of truth.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from rationalevault.organization.activity import OrganizationActivityState
from rationalevault.organization.graph import OrganizationGraphState
from rationalevault.organization.models import OrganizationState
from rationalevault.organization.utils import resolve_compiled_at
from rationalevault.organization.recommendations.models import (
    EvidenceType,
    Recommendation,
    RecommendationCategory,
    RecommendationSet,
    make_recommendation,
)

FLOW_IMBALANCE_THRESHOLD: int = -3
MIN_INVARIANT_COUNT_FOR_REVIEW: int = 3
MIN_CLUSTER_COHESION_FOR_REVIEW: float = 0.5


def _cluster_id(project_ids: list[str]) -> str:
    """Stable cluster identifier from sorted project IDs."""
    return hashlib.sha256(
        ",".join(sorted(project_ids)).encode()
    ).hexdigest()[:12]


class RecommendationEngine:
    """Deterministic recommendation engine. No LLM. No state. No persistence."""

    @staticmethod
    def generate(
        org_state: OrganizationState | None = None,
        graph_state: OrganizationGraphState | None = None,
        activity_state: OrganizationActivityState | None = None,
        reference_time: datetime | None = None,
    ) -> RecommendationSet:
        """Generate a RecommendationSet from projected organizational state.

        Any state may be None — engine degrades gracefully.
        """
        recommendations: list[Recommendation] = []

        if graph_state is not None:
            recommendations.extend(
                RecommendationEngine._resolve_conflicts(graph_state)
            )
            recommendations.extend(
                RecommendationEngine._rebalance_flow(graph_state)
            )
            recommendations.extend(
                RecommendationEngine._improve_clusters(graph_state)
            )

        if activity_state is not None:
            recommendations.extend(
                RecommendationEngine._review_inactive(activity_state)
            )
            recommendations.extend(
                RecommendationEngine._followup_transfers(activity_state)
            )

        if org_state is not None:
            recommendations.extend(
                RecommendationEngine._review_invariants(org_state)
            )

        deduped = RecommendationEngine._deduplicate(recommendations)
        sorted_recs = sorted(deduped, key=lambda r: r.priority)

        return RecommendationSet(
            compiled_at=resolve_compiled_at(reference_time),
            recommendations=sorted_recs,
        )

    @staticmethod
    def _deduplicate(
        recommendations: list[Recommendation],
    ) -> list[Recommendation]:
        """Deduplicate by recommendation_id.

        Two recommendations are considered duplicates if they have the same
        recommendation_id, which is derived from:
            sha256(f"{category}:{sorted(affected_projects)}:{sorted(evidence_ids)}")

        This means:
        - Same category + same project + same evidence → deduplicated
        - Same category + same project + different evidence → NOT deduplicated
        - Different categories → NOT deduplicated

        Current behavior is correct for I15 evidence patterns.
        If evidence ID scoping changes in the future, deduplication
        may need to be revisited.
        """
        seen: set[str] = set()
        result: list[Recommendation] = []
        for rec in recommendations:
            if rec.recommendation_id not in seen:
                seen.add(rec.recommendation_id)
                result.append(rec)
        return result

    @staticmethod
    def _resolve_conflicts(
        graph_state: OrganizationGraphState,
    ) -> list[Recommendation]:
        if not graph_state.contradiction_hotspots:
            return []

        result: list[Recommendation] = []
        for pid, score in graph_state.contradiction_hotspots:
            evidence = [f"{EvidenceType.HOTSPOT.value}:{pid}"]
            result.append(make_recommendation(
                category=RecommendationCategory.CONFLICT_RESOLUTION,
                title=f"Resolve {int(score)} contradiction(s) involving project '{pid}'",
                rationale=[
                    f"Project '{pid}' has {int(score)} contradiction(s)",
                    "Contradictions reduce knowledge reliability across the organization",
                ],
                affected_projects=[pid],
                evidence_ids=evidence,
            ))

        return result

    @staticmethod
    def _review_inactive(
        activity_state: OrganizationActivityState,
    ) -> list[Recommendation]:
        if not activity_state.inactive_projects:
            return []

        result: list[Recommendation] = []
        for pid in activity_state.inactive_projects:
            evidence = [f"{EvidenceType.INACTIVE.value}:{pid}"]
            result.append(make_recommendation(
                category=RecommendationCategory.INACTIVITY_REVIEW,
                title=f"Review inactive project '{pid}'",
                rationale=[
                    f"Project '{pid}' had no activity in the last {activity_state.activity_window_hours}h",
                    "Inactive projects may indicate blockers, completion, or abandonment",
                ],
                affected_projects=[pid],
                evidence_ids=evidence,
            ))

        return result

    @staticmethod
    def _followup_transfers(
        activity_state: OrganizationActivityState,
    ) -> list[Recommendation]:
        if not activity_state.recent_transfers:
            return []

        result: list[Recommendation] = []
        for transfer in activity_state.recent_transfers:
            evidence = [f"{EvidenceType.TRANSFER.value}:{transfer.knowledge_id}"]
            result.append(make_recommendation(
                category=RecommendationCategory.TRANSFER_FOLLOWUP,
                title=f"Follow up on knowledge transfer to '{transfer.target_project}'",
                rationale=[
                    f"'{transfer.knowledge_title}' transferred from '{transfer.source_project}' to '{transfer.target_project}'",
                    "New transfers may require validation, documentation, or integration",
                ],
                affected_projects=[transfer.target_project, transfer.source_project],
                evidence_ids=evidence,
            ))

        return result

    @staticmethod
    def _rebalance_flow(
        graph_state: OrganizationGraphState,
    ) -> list[Recommendation]:
        imbalanced = [
            (pid, balance) for pid, balance in graph_state.knowledge_flow_balance.items()
            if balance < FLOW_IMBALANCE_THRESHOLD
        ]
        if not imbalanced:
            return []

        imbalanced.sort(key=lambda x: x[1])
        result: list[Recommendation] = []
        for pid, balance in imbalanced:
            evidence = [f"{EvidenceType.FLOW.value}:{pid}"]
            result.append(make_recommendation(
                category=RecommendationCategory.FLOW_REBALANCING,
                title=f"Support knowledge consumer '{pid}' (flow balance: {balance})",
                rationale=[
                    f"Project '{pid}' has a flow balance of {balance}",
                    "Extreme consumers may be bottlenecked by knowledge dependencies",
                ],
                affected_projects=[pid],
                evidence_ids=evidence,
            ))

        return result

    @staticmethod
    def _improve_clusters(
        graph_state: OrganizationGraphState,
    ) -> list[Recommendation]:
        if not graph_state.clusters:
            return []
        if graph_state.health.cluster_cohesion >= MIN_CLUSTER_COHESION_FOR_REVIEW:
            return []

        cluster_evidence_ids: list[str] = []
        affected_projects: list[str] = []

        for cluster in graph_state.clusters:
            cid = _cluster_id(cluster)
            cluster_evidence_ids.append(f"{EvidenceType.CLUSTER.value}:{cid}")
            affected_projects.extend(cluster)

        return [make_recommendation(
            category=RecommendationCategory.CLUSTER_HEALTH,
            title="Improve organizational cluster cohesion",
            rationale=[
                f"Cluster cohesion: {graph_state.health.cluster_cohesion:.2f} (target: >= {MIN_CLUSTER_COHESION_FOR_REVIEW})",
                "Low cohesion indicates weak relationships within project clusters",
            ],
            affected_projects=list(set(affected_projects)),
            evidence_ids=cluster_evidence_ids,
        )]

    @staticmethod
    def _review_invariants(
        org_state: OrganizationState,
    ) -> list[Recommendation]:
        invariants = org_state.invariants_across_projects
        if len(invariants) < MIN_INVARIANT_COUNT_FOR_REVIEW:
            return []

        result: list[Recommendation] = []
        for inv in invariants:
            evidence = [f"{EvidenceType.INVARIANT.value}:{inv.knowledge_id}"]
            result.append(make_recommendation(
                category=RecommendationCategory.INVARIANT_REVIEW,
                title=f"Review organizational invariant: '{inv.title}'",
                rationale=[
                    f"Invariant '{inv.title}' spans {len(inv.present_in_projects)} project(s)",
                    "Organizational invariants should be periodically validated",
                ],
                affected_projects=inv.present_in_projects,
                evidence_ids=evidence,
            ))

        return result
