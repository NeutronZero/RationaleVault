"""Tests for I11.5 — Organization CLI and MCP Exposure."""
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
from rationalevault.organization.projection import OrganizationProjection
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


def _k(kid: str, title: str, project_id: str = "",
       transferability: str = KnowledgeTransferability.REUSABLE.value) -> KnowledgeObject:
    return KnowledgeObject(
        id=kid, version=1, title=title, content=f"content for {title}",
        knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=_conf(), importance="high", provenance=_prov(kid),
        supporting_memory_ids=[f"m-{kid}"],
        lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
        project_id=project_id,
        transferability=transferability,
    )


def _cpk(kid: str, title: str, source: str) -> CrossProjectKnowledge:
    return CrossProjectKnowledge(
        knowledge_id=kid, source_project_id=source,
        title=title, content=f"content for {title}",
        knowledge_type="ARCHITECTURE_PRINCIPLE",
        transferability="REUSABLE", confidence=0.9,
    )


def _make_state(project_id: str, knowledge: list[CrossProjectKnowledge]) -> CrossProjectState:
    by_project: dict[str, list[str]] = {}
    provenance: dict[str, str] = {}
    for k in knowledge:
        by_project.setdefault(k.source_project_id, []).append(k.knowledge_id)
        provenance[k.knowledge_id] = k.source_project_id
    return CrossProjectState(
        project_id=project_id, compiled_at="2026-01-01T00:00:00+00:00",
        source_projects=sorted(by_project.keys()),
        transferable_knowledge=knowledge,
        knowledge_by_project=by_project, provenance_map=provenance,
        health=CrossProjectHealth(1, len(knowledge), len(knowledge), 0, 1.0),
    )


def _registry() -> ProjectRegistry:
    return ProjectRegistry(projects=[
        ProjectEntry(id="proj_a", name="A", path="/a"),
        ProjectEntry(id="proj_b", name="B", path="/b"),
    ])


class TestCLIOrganizationStats:
    def test_stats_empty_projects(self) -> None:
        state = OrganizationProjection.project(
            registry=ProjectRegistry(projects=[]),
            cross_project_states={},
            knowledge_by_project={},
        )
        assert state.health.total_projects == 0

    def test_stats_with_transfer(self) -> None:
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
        assert d["health"]["total_projects"] == 1
        assert d["health"]["transferable_knowledge"] >= 1

    def test_stats_to_dict_serializable(self) -> None:
        s_b = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={"proj_b": s_b},
            knowledge_by_project={
                "proj_a": [_k("k1", "Use PG", "proj_a")],
                "proj_b": [],
            },
        )
        serialized = json.dumps(state.to_dict())
        assert isinstance(serialized, str)

    def test_stats_clusters(self) -> None:
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={},
            knowledge_by_project={
                "proj_a": [_k("k1", "Use PG", "proj_a")],
                "proj_b": [_k("k2", "Use PG", "proj_b")],
            },
        )
        assert len(state.project_clusters) >= 1

    def test_stats_telemetry(self) -> None:
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={},
            knowledge_by_project={
                "proj_a": [
                    _k("k1", "A", "proj_a", KnowledgeTransferability.LOCAL_ONLY.value),
                    _k("k2", "B", "proj_a", KnowledgeTransferability.REUSABLE.value),
                ],
            },
        )
        t = state.transferability_telemetry
        assert t.local_only_count == 1
        assert t.reusable_count == 1
        assert t.acceptance_rate == pytest.approx(0.5)


class TestCLIOrganizationLineage:
    def test_lineage_found(self) -> None:
        s_b = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={"proj_b": s_b},
            knowledge_by_project={
                "proj_a": [_k("k1", "Use PG", "proj_a")],
                "proj_b": [],
            },
        )
        lineage = state.active_lineages.get("k1")
        assert lineage is not None
        assert lineage.origin_project == "proj_a"
        assert "proj_b" in lineage.current_projects

    def test_lineage_not_found(self) -> None:
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={},
            knowledge_by_project={},
        )
        lineage = state.active_lineages.get("nonexistent")
        assert lineage is None

    def test_lineage_prefix_search(self) -> None:
        s_b = _make_state("proj_b", [_cpk("k1", "Use PG", "proj_a")])
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={"proj_b": s_b},
            knowledge_by_project={
                "proj_a": [_k("k1", "Use PG", "proj_a")],
                "proj_b": [],
            },
        )
        # Prefix search
        found = None
        for kid, l in state.active_lineages.items():
            if kid.startswith("k1"):
                found = l
                break
        assert found is not None


class TestMCPOrganizationState:
    def test_tool_returns_dict(self) -> None:
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
        assert "health" in d
        assert "transferability_telemetry" in d
        assert "active_lineages" in d

    def test_tool_empty_projects(self) -> None:
        state = OrganizationProjection.project(
            registry=ProjectRegistry(projects=[]),
            cross_project_states={},
            knowledge_by_project={},
        )
        d = state.to_dict()
        assert d["project_ids"] == []

    def test_tool_determinism(self) -> None:
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
        assert st1.health.to_dict() == st2.health.to_dict()

    def test_tool_conflicts(self) -> None:
        ka = _k("k1", "Auth", "proj_a")
        kb = KnowledgeObject(
            id="k2", version=1, title="Auth",
            content="content for Auth using OAuth2 flow",
            knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=_conf(), importance="high", provenance=_prov("k2"),
            supporting_memory_ids=["m2"], lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
            project_id="proj_b", transferability=KnowledgeTransferability.REUSABLE.value,
        )
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={},
            knowledge_by_project={
                "proj_a": [ka],
                "proj_b": [kb],
            },
        )
        d = state.to_dict()
        assert len(d["cross_project_conflicts"]) >= 1

    def test_tool_invariants(self) -> None:
        ka = KnowledgeObject(
            id="k1", version=1, title="No LLM", content="content for No LLM",
            knowledge_type=KnowledgeType.PROJECT_INVARIANT,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=_conf(), importance="critical", provenance=_prov("k1"),
            supporting_memory_ids=["m1"], lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
            project_id="proj_a", transferability=KnowledgeTransferability.ORGANIZATIONAL.value,
        )
        kb = KnowledgeObject(
            id="k2", version=1, title="No LLM", content="content for No LLM",
            knowledge_type=KnowledgeType.PROJECT_INVARIANT,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=_conf(), importance="critical", provenance=_prov("k2"),
            supporting_memory_ids=["m2"], lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
            project_id="proj_b", transferability=KnowledgeTransferability.ORGANIZATIONAL.value,
        )
        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={},
            knowledge_by_project={
                "proj_a": [ka],
                "proj_b": [kb],
            },
        )
        d = state.to_dict()
        assert len(d["invariants_across_projects"]) >= 1
