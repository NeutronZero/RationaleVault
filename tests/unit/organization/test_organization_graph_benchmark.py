"""Tests for I13.D — Organization Graph Benchmark."""
from __future__ import annotations

import pytest

from rationalevault.evaluation.organization_graph_benchmark import (
    OrganizationGraphBenchmarkCorpus,
    SCENARIOS,
)
from rationalevault.organization.graph import OrganizationGraphProjection
from rationalevault.organization.models import OrganizationState


class TestBenchmarkScenarios:
    def test_scenario_count(self) -> None:
        assert len(SCENARIOS) == 7

    def test_all_scenarios_unique(self) -> None:
        names = [s.name for s in SCENARIOS]
        assert len(names) == len(set(names))


class TestBenchmarkRunAll:
    def test_run_all(self) -> None:
        results = OrganizationGraphBenchmarkCorpus.run_all()
        assert len(results) == 7
        for r in results:
            assert r["all_passed"], f"Scenario {r['scenario']} failed: {r['checks']}"


class TestBenchmarkSingleProject:
    def test_single_project(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["alpha"])
        graph = OrganizationGraphProjection.project(org)
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 0
        assert graph.health.density == 0.0
        assert graph.health.connectivity == 1.0


class TestBenchmarkLinearTransfer:
    def test_linear_transfer(self) -> None:
        results = OrganizationGraphBenchmarkCorpus.run_all()
        linear = next(r for r in results if r["scenario"] == "linear_transfer")
        assert linear["all_passed"]


class TestBenchmarkBranchingTransfer:
    def test_branching_transfer(self) -> None:
        results = OrganizationGraphBenchmarkCorpus.run_all()
        branching = next(r for r in results if r["scenario"] == "branching_transfer")
        assert branching["all_passed"]


class TestBenchmarkContradictionHotspot:
    def test_contradiction_hotspot(self) -> None:
        results = OrganizationGraphBenchmarkCorpus.run_all()
        hotspot = next(r for r in results if r["scenario"] == "contradiction_hotspot")
        assert hotspot["all_passed"]


class TestBenchmarkClusterFormation:
    def test_cluster_formation(self) -> None:
        results = OrganizationGraphBenchmarkCorpus.run_all()
        cluster = next(r for r in results if r["scenario"] == "cluster_formation")
        assert cluster["all_passed"]


class TestBenchmarkDeterminism:
    def test_determinism(self) -> None:
        results = OrganizationGraphBenchmarkCorpus.run_all()
        det = next(r for r in results if r["scenario"] == "determinism")
        assert det["all_passed"]


class TestBenchmarkMetadataAccuracy:
    def test_metadata_accuracy(self) -> None:
        results = OrganizationGraphBenchmarkCorpus.run_all()
        meta = next(r for r in results if r["scenario"] == "metadata_accuracy")
        assert meta["all_passed"]


class TestBenchmarkOperations:
    def test_blast_radius(self) -> None:
        from rationalevault.organization.models import KnowledgeLineage
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c", "d"],
            active_lineages={
                "k1": KnowledgeLineage("k1", "a", ["b"], ["a", "b"], 1),
                "k2": KnowledgeLineage("k2", "b", ["c"], ["b", "c"], 1),
                "k3": KnowledgeLineage("k3", "c", ["d"], ["c", "d"], 1),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        radius = OrganizationGraphProjection.blast_radius(graph, "a")
        assert radius == {"a", "b", "c", "d"}

    def test_shortest_transfer_path(self) -> None:
        from rationalevault.organization.models import KnowledgeLineage
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c"],
            active_lineages={
                "k1": KnowledgeLineage("k1", "a", ["b"], ["a", "b"], 1),
                "k2": KnowledgeLineage("k2", "b", ["c"], ["b", "c"], 1),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        path = OrganizationGraphProjection.shortest_transfer_path(graph, "a", "c")
        assert path == ["a", "b", "c"]

    def test_project_centrality(self) -> None:
        from rationalevault.organization.models import KnowledgeLineage
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c"],
            active_lineages={
                "k1": KnowledgeLineage("k1", "a", ["b"], ["a", "b"], 1),
                "k2": KnowledgeLineage("k2", "a", ["c"], ["a", "c"], 1),
            },
        )
        graph = OrganizationGraphProjection.project(org)
        c = OrganizationGraphProjection.project_centrality(graph, "a")
        assert c > 0
