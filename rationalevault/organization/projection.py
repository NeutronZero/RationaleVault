"""RationaleVault Organization Projection — Organizational knowledge visibility.

OrganizationState = OrganizationProjection.project(registry, cross_project_states, knowledge_by_project)

Consumes CrossProjectState (deterministic view of primary state) and raw KnowledgeObjects.
No new persistence layer. Replayable from primary state.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional, ClassVar, Any
from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer

from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeTransferability,
)
from rationalevault.knowledge.project_registry import ProjectRegistry
from rationalevault.organization.models import (
    CrossProjectConflict,
    KnowledgeLineage,
    OrganizationHealth,
    OrganizationState,
    SharedKnowledge,
    TransferabilityTelemetry,
)
from rationalevault.projections.cross_project import CrossProjectState, CrossProjectProjection


def _lexical_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity of word tokens."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


def _deterministic_id(a: str, b: str) -> str:
    """SHA256 of sorted pair for deterministic conflict IDs."""
    pair = "|".join(sorted([a, b]))
    return hashlib.sha256(pair.encode()).hexdigest()[:16]


class OrganizationProjection(BaseProjection):
    """Builds organizational knowledge state from CrossProjectStates and raw KnowledgeObjects.

    CrossProjectState is treated as an optimization layer.
    KnowledgeObjects remain the authority. OrganizationProjection may use both.
    Deterministic: same inputs → identical output.
    """
    projection_name: ClassVar[str] = "Organization"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
    dependencies: ClassVar[list[type[BaseProjection]]] = [CrossProjectProjection]
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 50

    @staticmethod
    def project(
        registry: ProjectRegistry,
        cross_project_states: dict[str, CrossProjectState],
        knowledge_by_project: dict[str, list[KnowledgeObject]],
        *,
        include_telemetry: bool = True,
        reference_time: Optional[datetime] = None,
    ) -> OrganizationState:
        """Build organizational knowledge state.

        Args:
            registry: Project registry for metadata
            cross_project_states: Per-project CrossProjectState {project_id: state}
            knowledge_by_project: Raw KnowledgeObjects {project_id: [knowledge]}
            include_telemetry: Whether to compute telemetry (expensive at scale)
            reference_time: Optional reference time to run projection deterministically.

        Returns:
            OrganizationState with lineages, shared knowledge, conflicts, health
        """
        from rationalevault.organization.utils import resolve_compiled_at
        now = resolve_compiled_at(reference_time)
        project_ids = sorted(cross_project_states.keys())

        # 1. Active lineages (transferred knowledge only, best-effort)
        active_lineages = OrganizationProjection._compute_active_lineages(
            cross_project_states, knowledge_by_project,
        )

        # 2. Shared knowledge (independent of lineages)
        shared = OrganizationProjection._detect_shared_knowledge(cross_project_states)

        # 3. Cross-project conflicts (with evidence)
        conflicts = OrganizationProjection._detect_cross_project_conflicts(knowledge_by_project)

        # 4. Spanning invariants (first-class objects)
        invariants = OrganizationProjection._find_spanning_invariants(knowledge_by_project)

        # 5. Project clusters (similarity-based grouping)
        clusters = OrganizationProjection._cluster_projects(knowledge_by_project)

        # 6. Transferability telemetry
        telemetry = (
            OrganizationProjection._compute_telemetry(knowledge_by_project)
            if include_telemetry
            else TransferabilityTelemetry()
        )

        # 7. Health
        health = OrganizationProjection._compute_health(
            active_lineages, shared, conflicts, invariants, telemetry, len(project_ids),
        )

        return OrganizationState(
            compiled_at=now,
            project_ids=project_ids,
            active_lineages=active_lineages,
            shared_knowledge=shared,
            cross_project_conflicts=conflicts,
            invariants_across_projects=invariants,
            project_clusters=clusters,
            transferability_telemetry=telemetry,
            health=health,
        )

    # ── Internal Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _compute_active_lineages(
        cross_project_states: dict[str, CrossProjectState],
        knowledge_by_project: dict[str, list[KnowledgeObject]],
    ) -> dict[str, KnowledgeLineage]:
        """Compute lineages for transferred knowledge only. Best-effort transfer_path."""
        # Aggregate: for each knowledge_id, track all projects that hold it
        kid_projects: dict[str, set[str]] = {}
        kid_source: dict[str, str] = {}  # kid → source_project_id from CrossProjectState

        for proj_id, state in cross_project_states.items():
            for k in state.transferable_knowledge:
                # Transferred: source_project_id != requesting_project_id
                if k.source_project_id == state.project_id:
                    continue
                kid = k.knowledge_id
                if kid not in kid_projects:
                    kid_projects[kid] = set()
                kid_projects[kid].add(proj_id)
                kid_projects[kid].add(k.source_project_id)
                kid_source[kid] = k.source_project_id

        # Build lineages
        lineages: dict[str, KnowledgeLineage] = {}
        for kid, projects in kid_projects.items():
            # Determine origin from KnowledgeObject.project_id
            origin = kid_source.get(kid, "")
            for proj_id, klist in knowledge_by_project.items():
                for k in klist:
                    if k.id == kid and k.project_id:
                        origin = k.project_id
                        break

            # Best-effort transfer path from provenance_map
            transfer_path: list[str] = [origin]
            for proj_id, state in cross_project_states.items():
                if kid in state.provenance_map:
                    source = state.provenance_map[kid]
                    if source != transfer_path[-1]:
                        transfer_path.append(source)

            current = sorted(projects)
            lineages[kid] = KnowledgeLineage(
                knowledge_id=kid,
                origin_project=origin,
                current_projects=current,
                transfer_path=transfer_path,
                depth=max(0, len(transfer_path) - 1),
            )

        return lineages

    @staticmethod
    def _detect_shared_knowledge(
        cross_project_states: dict[str, CrossProjectState],
    ) -> list[SharedKnowledge]:
        """Detect knowledge present in multiple projects. Independent from lineages."""
        kid_projects: dict[str, set[str]] = {}
        kid_meta: dict[str, tuple[str, str]] = {}  # kid → (title, type)

        for proj_id, state in cross_project_states.items():
            for k in state.transferable_knowledge:
                kid = k.knowledge_id
                if kid not in kid_projects:
                    kid_projects[kid] = set()
                kid_projects[kid].add(proj_id)
                kid_meta[kid] = (k.title, k.knowledge_type)

        shared = []
        for kid, projects in kid_projects.items():
            if len(projects) > 1:
                title, ktype = kid_meta.get(kid, ("", ""))
                shared.append(SharedKnowledge(
                    knowledge_id=kid,
                    title=title,
                    knowledge_type=ktype,
                    present_in_projects=sorted(projects),
                    transfer_count=len(projects) - 1,
                ))

        return sorted(shared, key=lambda s: s.knowledge_id)

    @staticmethod
    def _detect_cross_project_conflicts(
        knowledge_by_project: dict[str, list[KnowledgeObject]],
    ) -> list[CrossProjectConflict]:
        """Detect contradictions across projects. Extensible for semantic matching."""
        conflicts: list[CrossProjectConflict] = []
        project_ids = sorted(knowledge_by_project.keys())

        for i, proj_a in enumerate(project_ids):
            for proj_b in project_ids[i + 1:]:
                klist_a = knowledge_by_project.get(proj_a, [])
                klist_b = knowledge_by_project.get(proj_b, [])

                # Index by (knowledge_type, normalized_title) for efficient matching
                type_title_index: dict[tuple[str, str], list[tuple[str, KnowledgeObject]]] = {}
                for k in klist_a:
                    key = (k.knowledge_type.value, k.title.lower())
                    type_title_index.setdefault(key, []).append((proj_a, k))

                for k_b in klist_b:
                    key = (k_b.knowledge_type.value, k_b.title.lower())
                    if key not in type_title_index:
                        continue
                    for proj_a_name, k_a in type_title_index[key]:
                        # Content must differ
                        if k_a.content == k_b.content:
                            continue
                        # Lexical similarity threshold
                        sim = _lexical_similarity(k_a.content, k_b.content)
                        if sim <= 0.3:
                            continue

                        reasons = ["same_title", "same_type", "content_divergence"]
                        conflict_id = _deterministic_id(k_a.id, k_b.id)
                        conflicts.append(CrossProjectConflict(
                            conflict_id=conflict_id,
                            knowledge_a_id=k_a.id,
                            knowledge_b_id=k_b.id,
                            project_a=proj_a_name,
                            project_b=proj_b,
                            knowledge_a_title=k_a.title,
                            knowledge_b_title=k_b.title,
                            confidence=sim,
                            reasons=reasons,
                        ))

        return sorted(conflicts, key=lambda c: c.conflict_id)

    @staticmethod
    def _find_spanning_invariants(
        knowledge_by_project: dict[str, list[KnowledgeObject]],
    ) -> list[SharedKnowledge]:
        """Find invariants spanning multiple projects. Returns first-class objects.
        
        Matches by (title, knowledge_type) across projects, not by ID.
        """
        # key = (normalized_title, knowledge_type) → set of project_ids
        key_projects: dict[tuple[str, str], set[str]] = {}
        key_meta: dict[tuple[str, str], tuple[str, str]] = {}

        for proj_id, klist in knowledge_by_project.items():
            for k in klist:
                is_invariant = (
                    k.knowledge_type.value == "PROJECT_INVARIANT"
                    or k.transferability == KnowledgeTransferability.ORGANIZATIONAL.value
                )
                if not is_invariant:
                    continue
                key = (k.title.lower(), k.knowledge_type.value)
                if key not in key_projects:
                    key_projects[key] = set()
                key_projects[key].add(proj_id)
                key_meta[key] = (k.title, k.knowledge_type.value)

        invariants = []
        for key, projects in key_projects.items():
            if len(projects) > 1:
                title, ktype = key_meta[key]
                invariants.append(SharedKnowledge(
                    knowledge_id=key[0],  # normalized title as ID
                    title=title,
                    knowledge_type=ktype,
                    present_in_projects=sorted(projects),
                    transfer_count=len(projects) - 1,
                ))

        return sorted(invariants, key=lambda s: s.knowledge_id)

    @staticmethod
    def _cluster_projects(
        knowledge_by_project: dict[str, list[KnowledgeObject]],
    ) -> list[list[str]]:
        """Cluster projects by knowledge similarity. Simple Jaccard + BFS."""
        if len(knowledge_by_project) <= 1:
            return [[p] for p in knowledge_by_project]

        project_ids = sorted(knowledge_by_project.keys())

        # Build term sets per project
        terms: dict[str, set[str]] = {}
        for pid in project_ids:
            words: set[str] = set()
            for k in knowledge_by_project.get(pid, []):
                words.update(k.title.lower().split())
            terms[pid] = words

        # Build adjacency via Jaccard > 0.0
        adj: dict[str, list[str]] = {p: [] for p in project_ids}
        for i, a in enumerate(project_ids):
            for b in project_ids[i + 1:]:
                ta, tb = terms[a], terms[b]
                if not ta or not tb:
                    continue
                intersection = ta & tb
                union = ta | tb
                if len(intersection) / len(union) > 0.0:
                    adj[a].append(b)
                    adj[b].append(a)

        # BFS connected components
        visited: set[str] = set()
        clusters: list[list[str]] = []
        for start in project_ids:
            if start in visited:
                continue
            component: list[str] = []
            queue = [start]
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                component.append(node)
                for neighbor in adj[node]:
                    if neighbor not in visited:
                        queue.append(neighbor)
            clusters.append(sorted(component))

        return sorted(clusters, key=lambda c: c[0])

    @staticmethod
    def _compute_telemetry(
        knowledge_by_project: dict[str, list[KnowledgeObject]],
    ) -> TransferabilityTelemetry:
        """Compute transferability distribution telemetry."""
        local_only = 0
        reusable = 0
        org_count = 0

        for klist in knowledge_by_project.values():
            for k in klist:
                if k.transferability == KnowledgeTransferability.LOCAL_ONLY.value:
                    local_only += 1
                elif k.transferability == KnowledgeTransferability.REUSABLE.value:
                    reusable += 1
                elif k.transferability == KnowledgeTransferability.ORGANIZATIONAL.value:
                    org_count += 1

        total = local_only + reusable + org_count
        matches = reusable + org_count
        acceptance = matches / total if total > 0 else 0.0

        return TransferabilityTelemetry(
            local_only_count=local_only,
            reusable_count=reusable,
            organizational_count=org_count,
            transfer_attempts=total,
            transfer_matches=matches,
            acceptance_rate=acceptance,
        )

    @staticmethod
    def _compute_health(
        active_lineages: dict[str, KnowledgeLineage],
        shared: list[SharedKnowledge],
        conflicts: list[CrossProjectConflict],
        invariants: list[SharedKnowledge],
        telemetry: TransferabilityTelemetry,
        project_count: int,
    ) -> OrganizationHealth:
        """Compute organizational health metrics."""
        total_knowledge = telemetry.transfer_attempts
        transferable = telemetry.transfer_matches
        shared_count = len(shared)
        adoption = shared_count / transferable if transferable > 0 else 0.0

        depths = [l.depth for l in active_lineages.values()]
        avg_depth = sum(depths) / len(depths) if depths else 0.0

        # Weighted overall score
        parts = []
        if project_count > 0:
            parts.append(min(1.0, project_count / 5))  # scales to 1.0 at 5 projects
        if transferable > 0:
            parts.append(min(1.0, adoption))
        parts.append(1.0 if not conflicts else max(0.0, 1.0 - len(conflicts) * 0.1))
        parts.append(min(1.0, len(invariants) / max(1, project_count)))
        overall = sum(parts) / len(parts) if parts else 1.0

        return OrganizationHealth(
            total_projects=project_count,
            total_knowledge=total_knowledge,
            transferable_knowledge=transferable,
            shared_knowledge_count=shared_count,
            knowledge_adoption_rate=adoption,
            cross_project_conflicts=len(conflicts),
            invariant_count=len(invariants),
            lineage_depth_avg=avg_depth,
            overall=overall,
        )
