"""RationaleVault Graph Projection Evaluator — Evaluates structural health of GraphState."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.evaluation.thresholds import EvaluationThresholds
from rationalevault.projections.graph import GraphState


@dataclass
class GraphProjectionEvalResult:
    """Evaluation result for graph projection structural health."""
    graph_connectivity: float
    referential_integrity: float
    determinism: float
    orphan_rate: float
    adjacency_consistency: float
    provenance_completeness: float
    cluster_consistency: float

    def passes_exit_gate(self) -> tuple[bool, list[str]]:
        """Check if all checks pass against thresholds."""
        t = EvaluationThresholds()
        failures: list[str] = []

        checks = {
            "graph_connectivity": (self.graph_connectivity, t.MIN_GP_CONNECTIVITY),
            "referential_integrity": (self.referential_integrity, t.MIN_GP_REFERENTIAL_INTEGRITY),
            "determinism": (self.determinism, t.MIN_GP_DETERMINISM),
            "adjacency_consistency": (self.adjacency_consistency, t.MIN_GP_ADJACENCY_CONSISTENCY),
            "provenance_completeness": (self.provenance_completeness, t.MIN_GP_PROVENANCE_COMPLETENESS),
            "cluster_consistency": (self.cluster_consistency, t.MIN_GP_CLUSTER_CONSISTENCY),
        }

        for name, (value, threshold) in checks.items():
            if value < threshold:
                failures.append(name)

        # Orphan rate is a maximum check (lower is better)
        if self.orphan_rate > t.MIN_GP_ORPHAN_RATE:
            failures.append("orphan_rate")

        return len(failures) == 0, failures

    def to_dict(self) -> dict[str, Any]:
        passed, failures = self.passes_exit_gate()
        checks = {
            "graph_connectivity": self.graph_connectivity,
            "referential_integrity": self.referential_integrity,
            "determinism": self.determinism,
            "orphan_rate": self.orphan_rate,
            "adjacency_consistency": self.adjacency_consistency,
            "provenance_completeness": self.provenance_completeness,
            "cluster_consistency": self.cluster_consistency,
        }
        passing = sum(1 for v in checks.values() if v >= 0.0)
        # Recompute properly: check against thresholds
        t = EvaluationThresholds()
        passing_count = 0
        total_count = len(checks)
        if self.graph_connectivity >= t.MIN_GP_CONNECTIVITY:
            passing_count += 1
        if self.referential_integrity >= t.MIN_GP_REFERENTIAL_INTEGRITY:
            passing_count += 1
        if self.determinism >= t.MIN_GP_DETERMINISM:
            passing_count += 1
        if self.orphan_rate <= t.MIN_GP_ORPHAN_RATE:
            passing_count += 1
        if self.adjacency_consistency >= t.MIN_GP_ADJACENCY_CONSISTENCY:
            passing_count += 1
        if self.provenance_completeness >= t.MIN_GP_PROVENANCE_COMPLETENESS:
            passing_count += 1
        if self.cluster_consistency >= t.MIN_GP_CLUSTER_CONSISTENCY:
            passing_count += 1

        return {
            **checks,
            "graph_projection_success_rate": passing_count / total_count if total_count > 0 else 1.0,
            "passed": passed,
            "failures": failures,
        }


class GraphProjectionEvaluator:
    """Evaluates structural health of a GraphState projection."""

    def evaluate(
        self,
        graph_state: GraphState,
        previous_state: GraphState | None = None,
    ) -> GraphProjectionEvalResult:
        """Evaluate graph projection health.

        Args:
            graph_state: The graph state to evaluate.
            previous_state: Optional duplicate build for determinism check.
        """
        return GraphProjectionEvalResult(
            graph_connectivity=self._check_connectivity(graph_state),
            referential_integrity=self._check_referential_integrity(graph_state),
            determinism=self._check_determinism(graph_state, previous_state),
            orphan_rate=self._check_orphan_rate(graph_state),
            adjacency_consistency=self._check_adjacency_consistency(graph_state),
            provenance_completeness=self._check_provenance_completeness(graph_state),
            cluster_consistency=self._check_cluster_consistency(graph_state),
        )

    def _check_connectivity(self, state: GraphState) -> float:
        """% of nodes in the largest connected component."""
        if not state.nodes:
            return 1.0
        if not state.clusters:
            return 0.0
        largest = max(len(c) for c in state.clusters)
        return largest / len(state.nodes)

    def _check_referential_integrity(self, state: GraphState) -> float:
        """% of edges with valid source AND target in nodes."""
        if not state.edges:
            return 1.0
        node_ids = set(state.nodes.keys())
        valid = sum(1 for e in state.edges if e.source in node_ids and e.target in node_ids)
        return valid / len(state.edges)

    def _check_determinism(
        self,
        state: GraphState,
        previous_state: GraphState | None,
    ) -> float:
        """1.0 if duplicate projection produces identical structure."""
        if previous_state is None:
            return 1.0
        # Compare node sets
        if set(state.nodes.keys()) != set(previous_state.nodes.keys()):
            return 0.0
        # Compare edge counts
        if len(state.edges) != len(previous_state.edges):
            return 0.0
        # Compare adjacency structure (order-independent)
        for nid in state.nodes:
            state_edges = sorted(
                (e.target, e.relation_type) for e in state.adjacency.get(nid, [])
            )
            prev_edges = sorted(
                (e.target, e.relation_type) for e in previous_state.adjacency.get(nid, [])
            )
            if state_edges != prev_edges:
                return 0.0
            # Also check reverse adjacency
            state_rev = sorted(
                (e.source, e.relation_type) for e in state.reverse_adjacency.get(nid, [])
            )
            prev_rev = sorted(
                (e.source, e.relation_type) for e in previous_state.reverse_adjacency.get(nid, [])
            )
            if state_rev != prev_rev:
                return 0.0
        return 1.0

    def _check_orphan_rate(self, state: GraphState) -> float:
        """% of nodes with zero edges (lower is better)."""
        if not state.nodes:
            return 0.0
        orphans = sum(
            1 for nid in state.nodes
            if not state.adjacency.get(nid) and not state.reverse_adjacency.get(nid)
        )
        return orphans / len(state.nodes)

    def _check_adjacency_consistency(self, state: GraphState) -> float:
        """adjacency and reverse_adjacency are inverses of each other."""
        if not state.edges:
            return 1.0

        # Forward: for every edge in adjacency[X], X should appear in reverse_adjacency[edge.target]
        forward_ok = 0
        total_forward = 0
        for nid, edges in state.adjacency.items():
            for edge in edges:
                total_forward += 1
                rev_edges = state.reverse_adjacency.get(edge.target, [])
                if any(e.source == nid and e.relation_type == edge.relation_type for e in rev_edges):
                    forward_ok += 1

        # Backward: for every edge in reverse_adjacency[X], X should appear in adjacency[edge.source]
        backward_ok = 0
        total_backward = 0
        for nid, edges in state.reverse_adjacency.items():
            for edge in edges:
                total_backward += 1
                fwd_edges = state.adjacency.get(edge.source, [])
                if any(e.target == nid and e.relation_type == edge.relation_type for e in fwd_edges):
                    backward_ok += 1

        total = total_forward + total_backward
        if total == 0:
            return 1.0
        return (forward_ok + backward_ok) / total

    def _check_provenance_completeness(self, state: GraphState) -> float:
        """% of nodes with a provenance entry."""
        if not state.nodes:
            return 1.0
        with_provenance = sum(1 for nid in state.nodes if nid in state.provenance)
        return with_provenance / len(state.nodes)

    def _check_cluster_consistency(self, state: GraphState) -> float:
        """Clusters are disjoint and cover all nodes."""
        if not state.nodes:
            return 1.0
        if not state.clusters:
            return 0.0

        # Check all nodes covered
        all_clustered = set()
        for cluster in state.clusters:
            all_clustered.update(cluster)
        coverage = len(all_clustered & set(state.nodes.keys())) / len(state.nodes)

        # Check no overlaps
        seen = set()
        overlaps = 0
        for cluster in state.clusters:
            for nid in cluster:
                if nid in seen:
                    overlaps += 1
                seen.add(nid)

        if overlaps > 0:
            return 0.0

        return coverage


def check_graph_projection_gates(result: GraphProjectionEvalResult) -> tuple[bool, list[str]]:
    """Check if graph projection passes exit gates."""
    return result.passes_exit_gate()
