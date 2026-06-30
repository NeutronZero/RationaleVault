"""Tests for I11.2 — OrganizationProjection."""
from __future__ import annotations

import json

import pytest

from rationalevault.knowledge.models import (
    KnowledgeConfidence,
    KnowledgeDomain,
    KnowledgeLifecycle,
    KnowledgeObject,
    KnowledgeTransferability,
    KnowledgeType,
    ProvenanceChain,
)
from rationalevault.knowledge.project_registry import ProjectEntry, ProjectRegistry
from rationalevault.organization.projection import (
    OrganizationProjection,
    _deterministic_id,
    _lexical_similarity,
)
from rationalevault.projections.cross_project import (
    CrossProjectHealth,
    CrossProjectKnowledge,
    CrossProjectState,
)


def _conf() -> KnowledgeConfidence:
    return KnowledgeConfidence(
        memory_count=3, source_event_count=2, contradiction_count=0,
        average_memory_confidence=0.9, score=0.9,
    )


def _prov(kid: str) -> ProvenanceChain:
    return ProvenanceChain(
        knowledge_id=kid, source_memory_ids=["m1"],
        source_event_ids=["100"], synthesis_event_id="syn-1",
        confidence=_conf(), evidence_count=1,
    )


def _k(
    kid: str, title: str, project_id: str = "",
    transferability: str = KnowledgeTransferability.REUSABLE.value,
    ktype: KnowledgeType = KnowledgeType.ARCHITECTURE_PRINCIPLE,
) -> KnowledgeObject:
    return KnowledgeObject(
        id=kid, version=1, title=title, content=f"content for {title}",
        knowledge_type=ktype, knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=_conf(), importance="high", provenance=_prov(kid),
        supporting_memory_ids=[f"m-{kid}"],
        lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
        project_id=project_id,
        transferability=transferability,
    )


def _cpk(
    kid: str, title: str, source: str,
    transferability: str = KnowledgeTransferability.REUSABLE.value,
) -> CrossProjectKnowledge:
    return CrossProjectKnowledge(
        knowledge_id=kid, source_project_id=source,
        title=title, content=f"content for {title}",
        knowledge_type="ARCHITECTURE_PRINCIPLE",
        transferability=transferability, confidence=0.9,
    )


def _make_state(
    project_id: str,
    knowledge: list[CrossProjectKnowledge],
) -> CrossProjectState:
    by_project: dict[str, list[str]] = {}
    provenance: dict[str, str] = {}
    for k in knowledge:
        by_project.setdefault(k.source_project_id, []).append(k.knowledge_id)
        provenance[k.knowledge_id] = k.source_project_id

    return CrossProjectState(
        project_id=project_id,
        compiled_at="2026-01-01T00:00:00+00:00",
        source_projects=sorted(by_project.keys()),
        transferable_knowledge=knowledge,
        knowledge_by_project=by_project,
        provenance_map=provenance,
        health=CrossProjectHealth(
            total_projects=1, total_transferable=len(knowledge),
            reusable_count=len(knowledge), organizational_count=0, coverage=1.0,
        ),
    )


def _registry() -> ProjectRegistry:
    return ProjectRegistry(projects=[
        ProjectEntry(id="proj_a", name="A", path="/a"),
        ProjectEntry(id="proj_b", name="B", path="/b"),
    ])


class TestHelpers:
    def test_lexical_similarity_identical(self) -> None:
        assert _lexical_similarity("hello world", "hello world") == 1.0

    def test_lexical_similarity_disjoint(self) -> None:
        assert _lexical_similarity("hello", "world") == 0.0

    def test_lexical_similarity_partial(self) -> None:
        sim = _lexical_similarity("use postgres for storage", "use redis for cache")
        assert 0.0 < sim < 1.0

    def test_lexical_similarity_empty(self) -> None:
        assert _lexical_similarity("", "hello") == 0.0

    def test_deterministic_id(self) -> None:
        id1 = _deterministic_id("a", "b")
        id2 = _deterministic_id("b", "a")
        assert id1 == id2

    def test_deterministic_id_different(self) -> None:
        assert _deterministic_id("a", "b") != _deterministic_id("a", "c")


class TestComputeActiveLineages:
    def test_empty_states(self) -> None:
        lineages = OrganizationProjection._compute_active_lineages({}, {})
        assert lineages == {}

    def test_transferred_knowledge_gets_lineage(self) -> None:
        state_b = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        states = {"proj_b": state_b}
        kb = {
            "proj_a": [_k("k1", "Use PG", "proj_a")],
            "proj_b": [],
        }
        lineages = OrganizationProjection._compute_active_lineages(states, kb)
        assert "k1" in lineages
        assert lineages["k1"].origin_project == "proj_a"
        assert "proj_b" in lineages["k1"].current_projects

    def test_native_knowledge_no_lineage(self) -> None:
        state_a = _make_state("proj_a", [])
        states = {"proj_a": state_a}
        kb = {"proj_a": [_k("k1", "Use PG", "proj_a")]}
        lineages = OrganizationProjection._compute_active_lineages(states, kb)
        assert "k1" not in lineages

    def test_depth_computed(self) -> None:
        state_b = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        states = {"proj_b": state_b}
        kb = {"proj_a": [_k("k1", "Use PG", "proj_a")]}
        lineages = OrganizationProjection._compute_active_lineages(states, kb)
        assert lineages["k1"].depth >= 0


class TestDetectSharedKnowledge:
    def test_empty(self) -> None:
        shared = OrganizationProjection._detect_shared_knowledge({})
        assert shared == []

    def test_single_project(self) -> None:
        state = _make_state("proj_a", [_cpk("k1", "Use PG", "proj_b")])
        shared = OrganizationProjection._detect_shared_knowledge({"proj_a": state})
        assert len(shared) == 0  # only in 1 project's transferable list

    def test_shared_across_projects(self) -> None:
        s1 = _make_state("proj_a", [_cpk("k1", "Use PG", "proj_b")])
        s2 = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        shared = OrganizationProjection._detect_shared_knowledge({"proj_a": s1, "proj_b": s2})
        assert len(shared) == 1
        assert shared[0].knowledge_id == "k1"
        assert len(shared[0].present_in_projects) == 2

    def test_independent_from_lineage(self) -> None:
        s1 = _make_state("proj_a", [_cpk("k1", "Use PG", "proj_b")])
        s2 = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        shared = OrganizationProjection._detect_shared_knowledge({"proj_a": s1, "proj_b": s2})
        # Shared even if transfer_count is computed
        assert shared[0].transfer_count >= 1


class TestDetectCrossProjectConflicts:
    def test_empty(self) -> None:
        conflicts = OrganizationProjection._detect_cross_project_conflicts({})
        assert conflicts == []

    def test_same_title_same_content_no_conflict(self) -> None:
        kb = {
            "proj_a": [_k("k1", "Auth", "proj_a")],
            "proj_b": [_k("k2", "Auth", "proj_b")],
        }
        conflicts = OrganizationProjection._detect_cross_project_conflicts(kb)
        assert len(conflicts) == 0

    def test_same_title_different_content_conflict(self) -> None:
        ka = _k("k1", "Auth", "proj_a")
        kb_obj = _k("k2", "Auth", "proj_b")
        kb_obj = KnowledgeObject(
            id=kb_obj.id, version=1, title="Auth",
            content="content for Auth using a different authentication system",
            knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=_conf(), importance="high", provenance=_prov(kb_obj.id),
            supporting_memory_ids=["m2"], lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
            project_id="proj_b", transferability=KnowledgeTransferability.REUSABLE.value,
        )
        conflicts = OrganizationProjection._detect_cross_project_conflicts({
            "proj_a": [ka], "proj_b": [kb_obj],
        })
        assert len(conflicts) == 1
        assert "same_title" in conflicts[0].reasons
        assert "same_type" in conflicts[0].reasons
        assert "content_divergence" in conflicts[0].reasons

    def test_different_title_no_conflict(self) -> None:
        kb = {
            "proj_a": [_k("k1", "Auth", "proj_a")],
            "proj_b": [_k("k2", "Storage", "proj_b")],
        }
        conflicts = OrganizationProjection._detect_cross_project_conflicts(kb)
        assert len(conflicts) == 0

    def test_deterministic_conflict_ids(self) -> None:
        ka = _k("k1", "Auth", "proj_a")
        kb_obj = KnowledgeObject(
            id="k2", version=1, title="Auth",
            content="content for Auth using a different system approach",
            knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=_conf(), importance="high", provenance=_prov("k2"),
            supporting_memory_ids=["m2"], lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
            project_id="proj_b", transferability=KnowledgeTransferability.REUSABLE.value,
        )
        c1 = OrganizationProjection._detect_cross_project_conflicts({
            "proj_a": [ka], "proj_b": [kb_obj],
        })
        c2 = OrganizationProjection._detect_cross_project_conflicts({
            "proj_a": [ka], "proj_b": [kb_obj],
        })
        assert c1[0].conflict_id == c2[0].conflict_id


class TestFindSpanningInvariants:
    def test_empty(self) -> None:
        inv = OrganizationProjection._find_spanning_invariants({})
        assert inv == []

    def test_project_invariant_across_projects(self) -> None:
        kb = {
            "proj_a": [_k("k1", "No LLM", "proj_a", ktype=KnowledgeType.PROJECT_INVARIANT)],
            "proj_b": [_k("k2", "No LLM", "proj_b", ktype=KnowledgeType.PROJECT_INVARIANT)],
        }
        inv = OrganizationProjection._find_spanning_invariants(kb)
        assert len(inv) == 1
        assert inv[0].knowledge_type == "PROJECT_INVARIANT"

    def test_organizational_across_projects(self) -> None:
        kb = {
            "proj_a": [_k("k1", "CI/CD", "proj_a", transferability=KnowledgeTransferability.ORGANIZATIONAL.value)],
            "proj_b": [_k("k2", "CI/CD", "proj_b", transferability=KnowledgeTransferability.ORGANIZATIONAL.value)],
        }
        inv = OrganizationProjection._find_spanning_invariants(kb)
        assert len(inv) == 1

    def test_single_project_no_span(self) -> None:
        kb = {
            "proj_a": [_k("k1", "No LLM", "proj_a", ktype=KnowledgeType.PROJECT_INVARIANT)],
        }
        inv = OrganizationProjection._find_spanning_invariants(kb)
        assert len(inv) == 0


class TestClusterProjects:
    def test_empty(self) -> None:
        clusters = OrganizationProjection._cluster_projects({})
        assert clusters == []

    def test_single_project(self) -> None:
        clusters = OrganizationProjection._cluster_projects({"a": []})
        assert clusters == [["a"]]

    def test_similar_projects_clustered(self) -> None:
        kb = {
            "proj_a": [_k("k1", "Use PostgreSQL for storage", "proj_a")],
            "proj_b": [_k("k2", "Use PostgreSQL for cache", "proj_b")],
            "proj_c": [_k("k3", "Machine learning pipeline", "proj_c")],
        }
        clusters = OrganizationProjection._cluster_projects(kb)
        assert len(clusters) == 2

    def test_deterministic(self) -> None:
        kb = {
            "a": [_k("k1", "Use PG", "a")],
            "b": [_k("k2", "Use PG", "b")],
        }
        c1 = OrganizationProjection._cluster_projects(kb)
        c2 = OrganizationProjection._cluster_projects(kb)
        assert c1 == c2


class TestComputeTelemetry:
    def test_mixed_distribution(self) -> None:
        kb = {
            "proj_a": [
                _k("k1", "A", "proj_a", transferability=KnowledgeTransferability.LOCAL_ONLY.value),
                _k("k2", "B", "proj_a", transferability=KnowledgeTransferability.REUSABLE.value),
                _k("k3", "C", "proj_a", transferability=KnowledgeTransferability.ORGANIZATIONAL.value),
            ],
        }
        t = OrganizationProjection._compute_telemetry(kb)
        assert t.local_only_count == 1
        assert t.reusable_count == 1
        assert t.organizational_count == 1
        assert t.transfer_attempts == 3
        assert t.transfer_matches == 2
        assert t.acceptance_rate == pytest.approx(2 / 3)

    def test_empty(self) -> None:
        t = OrganizationProjection._compute_telemetry({})
        assert t.transfer_attempts == 0
        assert t.acceptance_rate == 0.0


class TestProjectMethod:
    def test_empty_inputs(self) -> None:
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={},
            knowledge_by_project={},
        )
        assert state.project_ids == []
        assert state.health.total_projects == 0

    def test_two_projects_with_transfer(self) -> None:
        s_b = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={"proj_b": s_b},
            knowledge_by_project={
                "proj_a": [_k("k1", "Use PG", "proj_a")],
                "proj_b": [],
            },
        )
        assert "proj_b" in state.project_ids
        assert len(state.active_lineages) == 1
        assert state.health.total_projects == 1

    def test_determinism(self) -> None:
        s_b = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        kwargs = dict(
            registry=_registry(),
            cross_project_states={"proj_b": s_b},
            knowledge_by_project={
                "proj_a": [_k("k1", "Use PG", "proj_a")],
                "proj_b": [],
            },
        )
        st1 = OrganizationProjection.project(**kwargs)
        st2 = OrganizationProjection.project(**kwargs)
        assert st1.active_lineages == st2.active_lineages
        assert st1.shared_knowledge == st2.shared_knowledge
        assert st1.cross_project_conflicts == st2.cross_project_conflicts

    def test_to_dict_serializable(self) -> None:
        s_b = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={"proj_b": s_b},
            knowledge_by_project={
                "proj_a": [_k("k1", "Use PG", "proj_a")],
                "proj_b": [],
            },
        )
        d = state.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_include_telemetry_false(self) -> None:
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={},
            knowledge_by_project={},
            include_telemetry=False,
        )
        assert state.transferability_telemetry.transfer_attempts == 0

    def test_clusters_populated(self) -> None:
        s_b = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={"proj_b": s_b},
            knowledge_by_project={
                "proj_a": [_k("k1", "Use PG", "proj_a")],
                "proj_b": [_k("k2", "Use PG", "proj_b")],
            },
        )
        assert len(state.project_clusters) >= 1
