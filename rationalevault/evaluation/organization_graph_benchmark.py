"""Organization Graph Benchmark — Test scenarios for OrganizationGraphProjection."""
from __future__ import annotations

from dataclasses import dataclass, field

from rationalevault.organization.graph import OrganizationGraphProjection
from rationalevault.organization.models import (
    CrossProjectConflict,
    KnowledgeLineage,
    OrganizationState,
    SharedKnowledge,
)


def _lineage(kid: str, origin: str, current: list[str]) -> KnowledgeLineage:
    return KnowledgeLineage(
        knowledge_id=kid, origin_project=origin,
        current_projects=current, transfer_path=[origin] + current, depth=len(current),
    )


def _shared(kid: str, title: str, projects: list[str]) -> SharedKnowledge:
    return SharedKnowledge(
        knowledge_id=kid, title=title, knowledge_type="principle",
        present_in_projects=projects, transfer_count=len(projects) - 1,
    )


def _conflict(pa: str, pb: str, confidence: float = 0.8) -> CrossProjectConflict:
    return CrossProjectConflict(
        conflict_id=f"{pa}_{pb}", knowledge_a_id=f"k_{pa}", knowledge_b_id=f"k_{pb}",
        project_a=pa, project_b=pb, knowledge_a_title="A", knowledge_b_title="B",
        confidence=confidence, reasons=["lexical_similarity"],
    )


@dataclass
class OrganizationGraphBenchmarkScenario:
    name: str
    description: str
    org_state: OrganizationState
    expected_node_count: int = 0
    expected_edge_types: set[str] = field(default_factory=set)
    expected_producers: list[str] = field(default_factory=list)
    expected_consumers: list[str] = field(default_factory=list)


SCENARIOS: list[OrganizationGraphBenchmarkScenario] = [
    # 1. Single project
    OrganizationGraphBenchmarkScenario(
        name="single_project",
        description="Single isolated project with no edges",
        org_state=OrganizationState(
            compiled_at="2025-01-01", project_ids=["alpha"],
        ),
        expected_node_count=1,
        expected_edge_types=set(),
    ),

    # 2. Linear transfer chain
    OrganizationGraphBenchmarkScenario(
        name="linear_transfer",
        description="Linear transfer chain: A → B → C",
        org_state=OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _lineage("k1", "a", ["b"]),
                "k2": _lineage("k2", "b", ["c"]),
            },
        ),
        expected_node_count=3,
        expected_edge_types={"TRANSFERRED_TO"},
        expected_producers=["a"],
        expected_consumers=["c"],
    ),

    # 3. Branching transfer
    OrganizationGraphBenchmarkScenario(
        name="branching_transfer",
        description="Branching transfer: A → B, A → C",
        org_state=OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _lineage("k1", "a", ["b"]),
                "k2": _lineage("k2", "a", ["c"]),
                "k3": _lineage("k3", "a", ["b"]),
            },
        ),
        expected_node_count=3,
        expected_edge_types={"TRANSFERRED_TO"},
        expected_producers=["a"],
    ),

    # 4. Contradiction hotspot
    OrganizationGraphBenchmarkScenario(
        name="contradiction_hotspot",
        description="Contradiction hotspot: A ↔ B with multiple conflicts",
        org_state=OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c"],
            cross_project_conflicts=[
                _conflict("a", "b", 0.8),
                _conflict("a", "b", 0.6),
                _conflict("a", "b", 0.9),
                _conflict("a", "c", 0.7),
            ],
        ),
        expected_node_count=3,
        expected_edge_types={"CONFLICTS_WITH"},
    ),

    # 5. Cluster formation
    OrganizationGraphBenchmarkScenario(
        name="cluster_formation",
        description="Three projects in cluster with shared knowledge",
        org_state=OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c"],
            project_clusters=[["a", "b", "c"]],
            shared_knowledge=[
                _shared("k1", "Knowledge 1", ["a", "b"]),
                _shared("k2", "Knowledge 2", ["a", "c"]),
            ],
            active_lineages={
                "k1": _lineage("k1", "a", ["a", "b"]),
                "k2": _lineage("k2", "b", ["b", "c"]),
            },
        ),
        expected_node_count=3,
        expected_edge_types={"SHARED_BY", "IN_CLUSTER", "TRANSFERRED_TO"},
    ),

    # 6. Determinism
    OrganizationGraphBenchmarkScenario(
        name="determinism",
        description="Same input produces identical graph",
        org_state=OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c"],
            active_lineages={
                "k1": _lineage("k1", "a", ["b"]),
                "k2": _lineage("k2", "a", ["c"]),
            },
            shared_knowledge=[_shared("k1", "Knowledge 1", ["a", "b"])],
            project_clusters=[["a", "b", "c"]],
        ),
        expected_node_count=3,
        expected_edge_types={"TRANSFERRED_TO", "SHARED_BY", "IN_CLUSTER"},
    ),

    # 7. Metadata accuracy
    OrganizationGraphBenchmarkScenario(
        name="metadata_accuracy",
        description="Node metadata matches source lineages",
        org_state=OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b", "c", "d"],
            active_lineages={
                "k1": _lineage("k1", "a", ["b"]),
                "k2": _lineage("k2", "a", ["c"]),
                "k3": _lineage("k3", "b", ["d"]),
                "k4": _lineage("k4", "a", ["d"]),
            },
        ),
        expected_node_count=4,
        expected_edge_types={"TRANSFERRED_TO"},
        expected_producers=["a"],
        expected_consumers=["d"],
    ),
]


class OrganizationGraphBenchmarkCorpus:
    """Runs benchmark scenarios against OrganizationGraphProjection."""

    @staticmethod
    def run_all() -> list[dict]:
        results = []
        for scenario in SCENARIOS:
            results.append(OrganizationGraphBenchmarkCorpus.run_scenario(scenario))
        return results

    @staticmethod
    def run_scenario(scenario: OrganizationGraphBenchmarkScenario) -> dict:
        graph = OrganizationGraphProjection.project(scenario.org_state)

        checks: list[dict] = []

        # Node count
        node_count_ok = len(graph.nodes) == scenario.expected_node_count
        checks.append({
            "check": "node_count",
            "expected": scenario.expected_node_count,
            "actual": len(graph.nodes),
            "passed": node_count_ok,
        })

        # Edge types present
        actual_types = {e.relation_type.value for e in graph.edges}
        edge_types_ok = scenario.expected_edge_types <= actual_types
        checks.append({
            "check": "edge_types",
            "expected": sorted(scenario.expected_edge_types),
            "actual": sorted(actual_types),
            "passed": edge_types_ok,
        })

        # Producers
        if scenario.expected_producers:
            actual_producers = [p for p, _ in graph.knowledge_producers]
            producers_ok = all(p in actual_producers for p in scenario.expected_producers)
            checks.append({
                "check": "producers",
                "expected": scenario.expected_producers,
                "actual": actual_producers[:5],
                "passed": producers_ok,
            })

        # Consumers
        if scenario.expected_consumers:
            actual_consumers = [c for c, _ in graph.knowledge_consumers]
            consumers_ok = all(c in actual_consumers for c in scenario.expected_consumers)
            checks.append({
                "check": "consumers",
                "expected": scenario.expected_consumers,
                "actual": actual_consumers[:5],
                "passed": consumers_ok,
            })

        # Determinism
        graph2 = OrganizationGraphProjection.project(scenario.org_state)
        determinism_ok = (
            len(graph.edges) == len(graph2.edges)
            and graph.knowledge_flow_balance == graph2.knowledge_flow_balance
        )
        checks.append({
            "check": "determinism",
            "expected": True,
            "actual": determinism_ok,
            "passed": determinism_ok,
        })

        # Health
        health_ok = graph.health.overall >= 0.0
        checks.append({
            "check": "health_computed",
            "expected": True,
            "actual": health_ok,
            "passed": health_ok,
        })

        all_passed = all(c["passed"] for c in checks)
        return {
            "scenario": scenario.name,
            "description": scenario.description,
            "all_passed": all_passed,
            "checks": checks,
        }
