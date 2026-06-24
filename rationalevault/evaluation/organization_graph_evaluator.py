"""RationaleVault Organization Graph Evaluator — Evaluates organization graph projection quality.

7 metrics: connectivity, referential_integrity, determinism, edge_completeness,
cluster_consistency, metadata_accuracy, flow_balance_accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rationalevault.evaluation.thresholds import EvaluationThresholds
from rationalevault.organization.graph import OrganizationGraphState, OrganizationGraphProjection
from rationalevault.organization.models import OrganizationState
from rationalevault.organization.relation_types import OrganizationRelationType


@dataclass
class OrganizationGraphEvalResult:
    """Evaluation result for organization graph projection."""
    connectivity: float = 0.0
    referential_integrity: float = 0.0
    determinism: float = 0.0
    edge_completeness: float = 0.0
    cluster_consistency: float = 0.0
    metadata_accuracy: float = 0.0
    flow_balance_accuracy: float = 0.0

    def passes_exit_gate(self) -> tuple[bool, list[str]]:
        """Check if all metrics pass thresholds."""
        t = EvaluationThresholds()
        failures: list[str] = []

        checks = {
            "connectivity": (self.connectivity, t.MIN_ORG_GRAPH_CONNECTIVITY),
            "referential_integrity": (self.referential_integrity, t.MIN_ORG_GRAPH_REFERENTIAL_INTEGRITY),
            "determinism": (self.determinism, t.MIN_ORG_GRAPH_DETERMINISM),
            "edge_completeness": (self.edge_completeness, t.MIN_ORG_GRAPH_EDGE_COMPLETENESS),
            "cluster_consistency": (self.cluster_consistency, t.MIN_ORG_GRAPH_CLUSTER_CONSISTENCY),
            "metadata_accuracy": (self.metadata_accuracy, t.MIN_ORG_GRAPH_METADATA_ACCURACY),
            "flow_balance_accuracy": (self.flow_balance_accuracy, t.MIN_ORG_GRAPH_FLOW_BALANCE_ACCURACY),
        }

        for name, (value, threshold) in checks.items():
            if value < threshold:
                failures.append(name)

        return len(failures) == 0, failures

    def to_dict(self) -> dict[str, Any]:
        passed, failures = self.passes_exit_gate()
        t = EvaluationThresholds()
        checks = {
            "connectivity": self.connectivity,
            "referential_integrity": self.referential_integrity,
            "determinism": self.determinism,
            "edge_completeness": self.edge_completeness,
            "cluster_consistency": self.cluster_consistency,
            "metadata_accuracy": self.metadata_accuracy,
            "flow_balance_accuracy": self.flow_balance_accuracy,
        }
        threshold_map = {
            "connectivity": t.MIN_ORG_GRAPH_CONNECTIVITY,
            "referential_integrity": t.MIN_ORG_GRAPH_REFERENTIAL_INTEGRITY,
            "determinism": t.MIN_ORG_GRAPH_DETERMINISM,
            "edge_completeness": t.MIN_ORG_GRAPH_EDGE_COMPLETENESS,
            "cluster_consistency": t.MIN_ORG_GRAPH_CLUSTER_CONSISTENCY,
            "metadata_accuracy": t.MIN_ORG_GRAPH_METADATA_ACCURACY,
            "flow_balance_accuracy": t.MIN_ORG_GRAPH_FLOW_BALANCE_ACCURACY,
        }
        total = len(checks)
        passing = sum(1 for name, value in checks.items() if value >= threshold_map[name])
        return {
            **checks,
            "org_graph_success_rate": passing / total if total > 0 else 1.0,
            "passed": passed,
            "failures": failures,
        }


class OrganizationGraphEvaluator:
    """Evaluates organization graph projection quality."""

    def evaluate(
        self,
        graph_state: OrganizationGraphState,
        org_state: OrganizationState,
        previous_graph_state: OrganizationGraphState | None = None,
    ) -> OrganizationGraphEvalResult:
        """Evaluate organization graph projection.

        Args:
            graph_state: The organization graph state to evaluate.
            org_state: The source OrganizationState for completeness checks.
            previous_graph_state: Optional duplicate build for determinism check.
        """
        return OrganizationGraphEvalResult(
            connectivity=self._check_connectivity(graph_state),
            referential_integrity=self._check_referential_integrity(graph_state),
            determinism=self._check_determinism(graph_state, previous_graph_state),
            edge_completeness=self._check_edge_completeness(graph_state, org_state),
            cluster_consistency=self._check_cluster_consistency(graph_state, org_state),
            metadata_accuracy=self._check_metadata_accuracy(graph_state, org_state),
            flow_balance_accuracy=self._check_flow_balance_accuracy(graph_state),
        )

    def _check_connectivity(self, state: OrganizationGraphState) -> float:
        """% of nodes reachable from first node via BFS."""
        if not state.nodes:
            return 1.0
        start = next(iter(state.nodes))
        visited = OrganizationGraphProjection._bfs(start, state.adjacency)
        return len(visited) / len(state.nodes)

    def _check_referential_integrity(self, state: OrganizationGraphState) -> float:
        """% of edges where source and target exist in nodes."""
        if not state.edges:
            return 1.0
        valid = sum(
            1 for e in state.edges
            if e.source in state.nodes and e.target in state.nodes
        )
        return valid / len(state.edges)

    def _check_determinism(
        self,
        state: OrganizationGraphState,
        previous_state: OrganizationGraphState | None,
    ) -> float:
        """1.0 if duplicate projection produces identical graph."""
        if previous_state is None:
            return 1.0
        # Compare node sets
        if set(state.nodes.keys()) != set(previous_state.nodes.keys()):
            return 0.0
        # Compare edge count and weights
        if len(state.edges) != len(previous_state.edges):
            return 0.0
        # Compare flow balance
        if state.knowledge_flow_balance != previous_state.knowledge_flow_balance:
            return 0.0
        return 1.0

    def _check_edge_completeness(
        self,
        state: OrganizationGraphState,
        org_state: OrganizationState,
    ) -> float:
        """% of lineages + conflicts + shared knowledge represented as edges."""
        total_expected = 0
        total_found = 0

        # Check lineages → TRANSFERRED_TO edges
        transfer_edges = state.edges_by_relation.get(OrganizationRelationType.TRANSFERRED_TO, ())
        expected_transfers = set()
        for kid, lineage in org_state.active_lineages.items():
            for current_pid in lineage.current_projects:
                if current_pid != lineage.origin_project:
                    expected_transfers.add((lineage.origin_project, current_pid))
        found_transfers = {(e.source, e.target) for e in transfer_edges}
        total_expected += len(expected_transfers)
        total_found += len(expected_transfers & found_transfers)

        # Check conflicts → CONFLICTS_WITH edges
        conflict_edges = state.edges_by_relation.get(OrganizationRelationType.CONFLICTS_WITH, ())
        expected_conflicts = set()
        for conflict in org_state.cross_project_conflicts:
            pair = tuple(sorted([conflict.project_a, conflict.project_b]))
            expected_conflicts.add(pair)
        found_conflicts = {(e.source, e.target) for e in conflict_edges}
        total_expected += len(expected_conflicts)
        total_found += len(expected_conflicts & found_conflicts)

        # Check shared knowledge → SHARED_BY edges
        shared_edges = state.edges_by_relation.get(OrganizationRelationType.SHARED_BY, ())
        expected_shared = set()
        for sk in org_state.shared_knowledge:
            projects = sorted(sk.present_in_projects)
            for i in range(len(projects)):
                for j in range(i + 1, len(projects)):
                    expected_shared.add((projects[i], projects[j]))
        found_shared = {(e.source, e.target) for e in shared_edges}
        total_expected += len(expected_shared)
        total_found += len(expected_shared & found_shared)

        return total_found / total_expected if total_expected > 0 else 1.0

    def _check_cluster_consistency(
        self,
        state: OrganizationGraphState,
        org_state: OrganizationState,
    ) -> float:
        """IN_CLUSTER edges match project_clusters exactly."""
        if not org_state.project_clusters:
            return 1.0

        cluster_edges = state.edges_by_relation.get(OrganizationRelationType.IN_CLUSTER, ())
        expected_pairs = set()
        for cluster in org_state.project_clusters:
            for i in range(len(cluster)):
                for j in range(i + 1, len(cluster)):
                    expected_pairs.add((cluster[i], cluster[j]))

        found_pairs = {(e.source, e.target) for e in cluster_edges}
        if not expected_pairs:
            return 1.0

        return len(expected_pairs & found_pairs) / len(expected_pairs)

    def _check_metadata_accuracy(
        self,
        state: OrganizationGraphState,
        org_state: OrganizationState,
    ) -> float:
        """node.knowledge_count matches count of lineages where project is in current_projects."""
        if not state.nodes:
            return 1.0
        correct = 0
        for pid, node in state.nodes.items():
            expected_count = 0
            for kid, lineage in org_state.active_lineages.items():
                if pid in lineage.current_projects:
                    expected_count += 1
            if node.knowledge_count == expected_count:
                correct += 1
        return correct / len(state.nodes)

    def _check_flow_balance_accuracy(self, state: OrganizationGraphState) -> float:
        """knowledge_flow_balance matches transfer edges exactly."""
        if not state.nodes:
            return 1.0
        correct = 0
        for pid, expected_balance in state.knowledge_flow_balance.items():
            outbound = sum(
                int(e.weight) for e in state.adjacency.get(pid, [])
                if e.relation_type == OrganizationRelationType.TRANSFERRED_TO
            )
            inbound = sum(
                int(e.weight) for e in state.reverse_adjacency.get(pid, [])
                if e.relation_type == OrganizationRelationType.TRANSFERRED_TO
            )
            actual_balance = outbound - inbound
            if actual_balance == expected_balance:
                correct += 1
        return correct / len(state.nodes)


def check_organization_graph_gates(
    result: OrganizationGraphEvalResult,
    thresholds: EvaluationThresholds | None = None,
) -> tuple[bool, list[str]]:
    """Check if organization graph evaluation passes exit gates."""
    if thresholds is None:
        thresholds = EvaluationThresholds()
    return result.passes_exit_gate()
