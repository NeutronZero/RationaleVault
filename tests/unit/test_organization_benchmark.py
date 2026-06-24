"""Tests for I11.4 — Organization Benchmark Corpus."""
from __future__ import annotations

import json

import pytest

from rationalevault.evaluation.organization_benchmark import (
    OrganizationBenchmarkCorpus,
    OrganizationBenchmarkScenario,
    build_organization_benchmark,
)
from rationalevault.knowledge.models import KnowledgeTransferability
from rationalevault.organization.projection import OrganizationProjection
from rationalevault.knowledge.project_registry import ProjectEntry, ProjectRegistry


def _registry() -> ProjectRegistry:
    return ProjectRegistry(projects=[
        ProjectEntry(id=pid, name=pid, path=f"/{pid}")
        for pid in ["proj_a", "proj_b", "proj_c"]
    ])


class TestBenchmarkCorpus:
    def test_corpus_has_scenarios(self) -> None:
        corpus = build_organization_benchmark()
        assert len(corpus.scenarios) >= 6

    def test_all_scenarios_have_names(self) -> None:
        corpus = build_organization_benchmark()
        for s in corpus.scenarios:
            assert s.name
            assert s.description

    def test_get_scenario(self) -> None:
        corpus = build_organization_benchmark()
        s = corpus.get_scenario("single_project")
        assert s is not None
        assert s.name == "single_project"

    def test_get_scenario_not_found(self) -> None:
        corpus = build_organization_benchmark()
        assert corpus.get_scenario("nonexistent") is None

    def test_all_scenarios_have_knowledge(self) -> None:
        corpus = build_organization_benchmark()
        for s in corpus.scenarios:
            assert len(s.knowledge_by_project) > 0

    def test_transferability_values_valid(self) -> None:
        corpus = build_organization_benchmark()
        valid = {t.value for t in KnowledgeTransferability}
        for s in corpus.scenarios:
            for klist in s.knowledge_by_project.values():
                for k in klist:
                    assert k.transferability in valid

    def test_determinism_scenario_runs(self) -> None:
        corpus = build_organization_benchmark()
        scenario = corpus.get_scenario("determinism")
        assert scenario is not None

        # Run projection twice
        state1 = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={},
            knowledge_by_project=scenario.knowledge_by_project,
        )
        state2 = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={},
            knowledge_by_project=scenario.knowledge_by_project,
        )
        # Deterministic
        assert state1.active_lineages == state2.active_lineages
        assert state1.shared_knowledge == state2.shared_knowledge

    def test_cross_project_contradiction_detected(self) -> None:
        corpus = build_organization_benchmark()
        scenario = corpus.get_scenario("cross_project_contradiction")
        assert scenario is not None

        # Build minimal cross_project_states for conflict detection
        from rationalevault.projections.cross_project import CrossProjectState, CrossProjectHealth, CrossProjectKnowledge
        states = {}
        for pid in scenario.knowledge_by_project:
            states[pid] = CrossProjectState(
                project_id=pid,
                compiled_at="2026-01-01T00:00:00+00:00",
                transferable_knowledge=[],
                health=CrossProjectHealth(1, 0, 0, 0, 0.0),
            )

        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states=states,
            knowledge_by_project=scenario.knowledge_by_project,
        )
        assert len(state.cross_project_conflicts) >= scenario.expected_conflict_count_min

    def test_invariant_spanning_detected(self) -> None:
        corpus = build_organization_benchmark()
        scenario = corpus.get_scenario("invariant_spanning")
        assert scenario is not None

        state = OrganizationProjection.project(
            registry=_registry(),
            cross_project_states={},
            knowledge_by_project=scenario.knowledge_by_project,
        )
        assert len(state.invariants_across_projects) >= scenario.expected_invariant_count_min

    def test_serializable(self) -> None:
        corpus = build_organization_benchmark()
        d = {"scenarios": [{"name": s.name, "desc": s.description} for s in corpus.scenarios]}
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
