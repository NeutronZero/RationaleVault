"""Relay Graph Evaluation — Evaluates the quality, integrity, and determinism of the projected graph."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from relay.knowledge.graph import GraphProjection
from relay.knowledge.models import KnowledgeObject, KnowledgeRelation


@dataclass
class GraphEvalResult:
    """Evaluation result for graph projection."""
    node_coverage: float
    edge_coverage: float
    referential_integrity: float
    determinism_score: float
    density: float
    connected_components: int
    orphan_count: int
    orphan_pct: float
    largest_component_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_coverage": self.node_coverage,
            "edge_coverage": self.edge_coverage,
            "referential_integrity": self.referential_integrity,
            "determinism_score": self.determinism_score,
            "density": self.density,
            "connected_components": self.connected_components,
            "orphan_count": self.orphan_count,
            "orphan_pct": self.orphan_pct,
            "largest_component_pct": self.largest_component_pct,
        }


def evaluate_graph_projection(
    projection: GraphProjection,
    knowledge_objects: list[KnowledgeObject],
    relations: list[KnowledgeRelation],
    previous_projection: Optional[GraphProjection] = None,
) -> GraphEvalResult:
    """Evaluate the projected graph against ground truth objects, relations, and determinism checks."""
    # Node Coverage: V / len(knowledge_objects)
    node_coverage = len(projection.nodes) / len(knowledge_objects) if knowledge_objects else 1.0

    # Edge Coverage: E / len(relations)
    edge_coverage = len(projection.edges) / len(relations) if relations else 1.0

    # Referential Integrity: check if all edges link existing nodes
    node_ids = {n.id for n in projection.nodes}
    valid_edges = sum(1 for e in projection.edges if e.source in node_ids and e.target in node_ids)
    referential_integrity = valid_edges / len(projection.edges) if projection.edges else 1.0

    # Determinism Score: identical builds should produce identical graph_ids
    determinism_score = 1.0
    if previous_projection is not None:
        determinism_score = 1.0 if projection.graph_id == previous_projection.graph_id else 0.0

    # Get baseline statistics from projection stats
    stats = projection.stats()

    return GraphEvalResult(
        node_coverage=node_coverage,
        edge_coverage=edge_coverage,
        referential_integrity=referential_integrity,
        determinism_score=determinism_score,
        density=stats["density"],
        connected_components=stats["connected_components"],
        orphan_count=stats["orphan_count"],
        orphan_pct=stats["orphan_pct"],
        largest_component_pct=stats["largest_component_pct"],
    )


def check_graph_gates(result: GraphEvalResult) -> tuple[bool, list[str]]:
    """Check if the evaluation passes Sprint I7.5 Exit Gates."""
    failures: list[str] = []

    # Hard Gates
    if result.node_coverage < 1.0:
        failures.append("node_coverage")
    if result.edge_coverage < 1.0:
        failures.append("edge_coverage")
    if result.referential_integrity < 1.0:
        failures.append("referential_integrity")
    if result.determinism_score < 1.0:
        failures.append("determinism_score")

    # Advisory / Density Gates
    if result.density < 0.10:
        failures.append("density")
    if result.orphan_pct > 0.50:
        failures.append("orphan_pct")

    return len(failures) == 0, failures
