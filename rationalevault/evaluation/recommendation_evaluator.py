"""RationaleVault Recommendation Evaluator — Evaluates recommendation engine quality.

7 metrics: recommendation_coverage, recommendation_precision, category_exclusivity,
evidence_integrity, priority_accuracy, recommendation_determinism, recommendation_replayability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rationalevault.evaluation.thresholds import EvaluationThresholds
from rationalevault.recommendations.engine import RecommendationEngine
from rationalevault.recommendations.models import (
    CATEGORY_PRIORITY,
    Recommendation,
    RecommendationCategory,
    RecommendationSet,
)


@dataclass
class RecommendationEvalResult:
    """Evaluation result for recommendation engine quality."""
    recommendation_coverage: float = 0.0
    recommendation_precision: float = 0.0
    category_exclusivity: float = 0.0
    evidence_integrity: float = 0.0
    priority_accuracy: float = 0.0
    recommendation_determinism: float = 0.0
    recommendation_replayability: float = 0.0

    def passes_exit_gate(self) -> tuple[bool, list[str]]:
        t = EvaluationThresholds()
        failures: list[str] = []

        checks = {
            "recommendation_coverage": (self.recommendation_coverage, t.MIN_I15_COVERAGE),
            "recommendation_precision": (self.recommendation_precision, t.MIN_I15_PRECISION),
            "category_exclusivity": (self.category_exclusivity, t.MIN_I15_CATEGORY_EXCLUSIVITY),
            "evidence_integrity": (self.evidence_integrity, t.MIN_I15_EVIDENCE_INTEGRITY),
            "priority_accuracy": (self.priority_accuracy, t.MIN_I15_PRIORITY_ACCURACY),
            "recommendation_determinism": (self.recommendation_determinism, t.MIN_I15_DETERMINISM),
            "recommendation_replayability": (self.recommendation_replayability, t.MIN_I15_REPLAYABILITY),
        }

        for name, (value, threshold) in checks.items():
            if value < threshold:
                failures.append(name)

        return len(failures) == 0, failures

    def to_dict(self) -> dict[str, Any]:
        passed, failures = self.passes_exit_gate()
        t = EvaluationThresholds()
        checks = {
            "recommendation_coverage": self.recommendation_coverage,
            "recommendation_precision": self.recommendation_precision,
            "category_exclusivity": self.category_exclusivity,
            "evidence_integrity": self.evidence_integrity,
            "priority_accuracy": self.priority_accuracy,
            "recommendation_determinism": self.recommendation_determinism,
            "recommendation_replayability": self.recommendation_replayability,
        }
        threshold_map = {
            "recommendation_coverage": t.MIN_I15_COVERAGE,
            "recommendation_precision": t.MIN_I15_PRECISION,
            "category_exclusivity": t.MIN_I15_CATEGORY_EXCLUSIVITY,
            "evidence_integrity": t.MIN_I15_EVIDENCE_INTEGRITY,
            "priority_accuracy": t.MIN_I15_PRIORITY_ACCURACY,
            "recommendation_determinism": t.MIN_I15_DETERMINISM,
            "recommendation_replayability": t.MIN_I15_REPLAYABILITY,
        }
        total = len(checks)
        passing = sum(1 for name, value in checks.items() if value >= threshold_map[name])
        overall = sum(checks.values()) / total if total > 0 else 1.0
        return {
            **checks,
            "overall": round(overall, 4),
            "recommendation_engine_success_rate": passing / total if total > 0 else 1.0,
            "passed": passed,
            "failures": failures,
        }


@dataclass
class RecommendationTestCase:
    """A single recommendation test case."""
    name: str
    org_state: Any = None
    graph_state: Any = None
    activity_state: Any = None
    expected_categories: list[str] = field(default_factory=list)
    expected_empty: bool = False
    expected_attention_load: float = 0.0
    expected_evidence_count: int = 0


def _make_hotspot_graph(hotspots: list[tuple[str, float]]) -> Any:
    """Build a minimal OrganizationGraphState with contradiction_hotspots."""
    from dataclasses import dataclass, field
    from rationalevault.organization.graph import OrganizationGraphHealth

    @dataclass
    class FakeOrgGraphState:
        contradiction_hotspots: list = field(default_factory=list)
        knowledge_flow_balance: dict = field(default_factory=dict)
        clusters: list = field(default_factory=list)
        health: Any = None

    return FakeOrgGraphState(
        contradiction_hotspots=hotspots,
        knowledge_flow_balance={},
        clusters=[],
        health=OrganizationGraphHealth(cluster_cohesion=1.0),
    )


def _make_inactive_activity(inactive: list[str], window_hours: int = 72) -> Any:
    """Build a minimal OrganizationActivityState with inactive_projects."""
    from dataclasses import dataclass, field

    @dataclass
    class FakeActivityState:
        inactive_projects: list = field(default_factory=list)
        active_projects: list = field(default_factory=list)
        project_count: int = 0
        activity_window_hours: int = 72
        recent_transfers: list = field(default_factory=list)
        recent_conflicts: list = field(default_factory=list)
        recent_knowledge: list = field(default_factory=list)
        recent_events_by_project: dict = field(default_factory=dict)
        compiled_at: str = ""

    return FakeActivityState(
        inactive_projects=inactive,
        active_projects=[],
        project_count=len(inactive),
        activity_window_hours=window_hours,
    )


def _make_transfer_activity(transfers: list[Any]) -> Any:
    """Build a minimal OrganizationActivityState with recent_transfers."""
    from dataclasses import dataclass, field

    @dataclass
    class FakeActivityState:
        inactive_projects: list = field(default_factory=list)
        active_projects: list = field(default_factory=list)
        project_count: int = 0
        activity_window_hours: int = 72
        recent_transfers: list = field(default_factory=list)
        recent_conflicts: list = field(default_factory=list)
        recent_knowledge: list = field(default_factory=list)
        recent_events_by_project: dict = field(default_factory=dict)
        compiled_at: str = ""

    return FakeActivityState(
        recent_transfers=transfers,
        inactive_projects=[],
        project_count=1,
    )


def _make_flow_graph(flow_balance: dict[str, int]) -> Any:
    """Build a minimal OrganizationGraphState with flow balance."""
    from dataclasses import dataclass, field
    from rationalevault.organization.graph import OrganizationGraphHealth

    @dataclass
    class FakeOrgGraphState:
        contradiction_hotspots: list = field(default_factory=list)
        knowledge_flow_balance: dict = field(default_factory=dict)
        clusters: list = field(default_factory=list)
        health: Any = None

    return FakeOrgGraphState(
        contradiction_hotspots=[],
        knowledge_flow_balance=flow_balance,
        clusters=[],
        health=OrganizationGraphHealth(cluster_cohesion=1.0),
    )


def _make_low_cohesion_graph(cohesion: float, clusters: list[list[str]]) -> Any:
    """Build a minimal OrganizationGraphState with low cluster cohesion."""
    from dataclasses import dataclass, field
    from rationalevault.organization.graph import OrganizationGraphHealth

    @dataclass
    class FakeOrgGraphState:
        contradiction_hotspots: list = field(default_factory=list)
        knowledge_flow_balance: dict = field(default_factory=dict)
        clusters: list = field(default_factory=list)
        health: Any = None

    return FakeOrgGraphState(
        contradiction_hotspots=[],
        knowledge_flow_balance={},
        clusters=clusters,
        health=OrganizationGraphHealth(cluster_cohesion=cohesion),
    )


def _make_invariant_org(invariants: list[Any], count: int = 0) -> Any:
    """Build a minimal OrganizationState with invariants_across_projects."""
    from dataclasses import dataclass, field

    @dataclass
    class FakeSharedKnowledge:
        knowledge_id: str = ""
        title: str = ""
        present_in_projects: list = field(default_factory=list)

    invariants = invariants or [
        FakeSharedKnowledge(knowledge_id="inv-1", title="Invariant A", present_in_projects=["p1", "p2"]),
        FakeSharedKnowledge(knowledge_id="inv-2", title="Invariant B", present_in_projects=["p3"]),
        FakeSharedKnowledge(knowledge_id="inv-3", title="Invariant C", present_in_projects=["p1", "p3"]),
    ]

    @dataclass
    class FakeOrgState:
        invariants_across_projects: list = field(default_factory=list)
        project_ids: list = field(default_factory=list)
        active_lineages: dict = field(default_factory=dict)
        cross_project_conflicts: list = field(default_factory=list)

    return FakeOrgState(
        invariants_across_projects=invariants,
        project_ids=["p1", "p2", "p3"],
    )


RECOMMENDATION_BENCHMARK_CORPUS: list[RecommendationTestCase] = [
    RecommendationTestCase(
        name="empty_state",
        graph_state=_make_hotspot_graph([]),
        activity_state=_make_inactive_activity([]),
        org_state=_make_invariant_org([]),
        expected_categories=[],
        expected_empty=True,
        expected_attention_load=0.0,
        expected_evidence_count=0,
    ),
    RecommendationTestCase(
        name="contradiction_hotspot",
        graph_state=_make_hotspot_graph([("project_a", 3.0)]),
        expected_categories=["CONFLICT_RESOLUTION"],
        expected_evidence_count=1,
    ),
    RecommendationTestCase(
        name="inactive_project",
        activity_state=_make_inactive_activity(["project_b"]),
        expected_categories=["INACTIVITY_REVIEW"],
        expected_evidence_count=1,
    ),
    RecommendationTestCase(
        name="recent_transfer",
        activity_state=_make_transfer_activity([
            type("Transfer", (), {"knowledge_id": "k1", "knowledge_title": "Pattern X",
                                  "source_project": "p1", "target_project": "p2"})(),
        ]),
        expected_categories=["TRANSFER_FOLLOWUP"],
        expected_evidence_count=1,
    ),
    RecommendationTestCase(
        name="negative_flow",
        graph_state=_make_flow_graph({"project_c": -5}),
        expected_categories=["FLOW_REBALANCING"],
        expected_evidence_count=1,
    ),
    RecommendationTestCase(
        name="low_cohesion",
        graph_state=_make_low_cohesion_graph(0.3, [["p1", "p2"]]),
        expected_categories=["CLUSTER_HEALTH"],
        expected_evidence_count=1,
    ),
    RecommendationTestCase(
        name="mixed_signals",
        graph_state=_make_hotspot_graph([("p1", 2.0)]),
        activity_state=_make_inactive_activity(["p2"]),
        expected_categories=["CONFLICT_RESOLUTION", "INACTIVITY_REVIEW"],
        expected_evidence_count=2,
    ),
    RecommendationTestCase(
        name="duplicate_signals",
        graph_state=_make_hotspot_graph([("p1", 2.0), ("p1", 3.0)]),
        expected_categories=["CONFLICT_RESOLUTION"],
        expected_evidence_count=1,
    ),
]


class RecommendationEvaluator:
    """Evaluates recommendation engine quality."""

    def __init__(self) -> None:
        self.engine = RecommendationEngine()

    def evaluate(
        self,
        corpus: list[RecommendationTestCase] | None = None,
        previous_results: dict[str, RecommendationSet] | None = None,
    ) -> RecommendationEvalResult:
        """Evaluate recommendation engine across a test corpus."""
        if corpus is None:
            corpus = RECOMMENDATION_BENCHMARK_CORPUS

        results: dict[str, RecommendationSet] = {}

        for tc in corpus:
            result = self.engine.generate(
                org_state=tc.org_state,
                graph_state=tc.graph_state,
                activity_state=tc.activity_state,
            )
            results[tc.name] = result

        return RecommendationEvalResult(
            recommendation_coverage=self._check_coverage(corpus, results),
            recommendation_precision=self._check_precision(corpus, results),
            category_exclusivity=self._check_category_exclusivity(corpus, results),
            evidence_integrity=self._check_evidence_integrity(corpus, results),
            priority_accuracy=self._check_priority_accuracy(corpus, results),
            recommendation_determinism=self._check_determinism(corpus, results),
            recommendation_replayability=self._check_replayability(corpus, previous_results),
        )

    def _check_coverage(
        self,
        corpus: list[RecommendationTestCase],
        results: dict[str, RecommendationSet],
    ) -> float:
        """% of expected categories that appear in generated recommendations."""
        if not corpus:
            return 1.0
        total_expected = 0.0
        total_matched = 0.0
        for tc in corpus:
            if not tc.expected_categories:
                continue
            result = results.get(tc.name)
            if result is None:
                continue
            generated = {r.category.value for r in result.recommendations}
            for expected in tc.expected_categories:
                total_expected += 1.0
                if expected in generated:
                    total_matched += 1.0
        return total_matched / total_expected if total_expected > 0 else 1.0

    def _check_precision(
        self,
        corpus: list[RecommendationTestCase],
        results: dict[str, RecommendationSet],
    ) -> float:
        """% of generated recommendations that are expected."""
        if not corpus:
            return 1.0
        total_generated = 0.0
        total_valid = 0.0
        for tc in corpus:
            result = results.get(tc.name)
            if result is None:
                continue
            expected_set = set(tc.expected_categories)
            for rec in result.recommendations:
                total_generated += 1.0
                if rec.category.value in expected_set:
                    total_valid += 1.0
            if tc.expected_empty:
                if len(result.recommendations) == 0:
                    total_valid += 1.0
                    total_generated += 1.0
        return total_valid / total_generated if total_generated > 0 else 1.0

    def _check_category_exclusivity(
        self,
        corpus: list[RecommendationTestCase],
        results: dict[str, RecommendationSet],
    ) -> float:
        """No recommendation appears without its triggering signal present."""
        if not corpus:
            return 1.0
        total_checks = 0.0
        total_valid = 0.0
        signal_map = {
            "CONFLICT_RESOLUTION": lambda tc: (
                tc.graph_state is not None
                and tc.graph_state.contradiction_hotspots
                and len(tc.graph_state.contradiction_hotspots) > 0
            ),
            "INACTIVITY_REVIEW": lambda tc: (
                tc.activity_state is not None
                and tc.activity_state.inactive_projects
            ),
            "TRANSFER_FOLLOWUP": lambda tc: (
                tc.activity_state is not None
                and tc.activity_state.recent_transfers
            ),
            "FLOW_REBALANCING": lambda tc: (
                tc.graph_state is not None
                and tc.graph_state.knowledge_flow_balance
                and any(v < -3 for v in tc.graph_state.knowledge_flow_balance.values())
            ),
            "CLUSTER_HEALTH": lambda tc: (
                tc.graph_state is not None
                and tc.graph_state.clusters
                and tc.graph_state.health is not None
                and tc.graph_state.health.cluster_cohesion < 0.5
            ),
            "INVARIANT_REVIEW": lambda tc: (
                tc.org_state is not None
                and len(tc.org_state.invariants_across_projects) >= 3
            ),
        }
        for tc in corpus:
            result = results.get(tc.name)
            if result is None:
                continue
            for rec in result.recommendations:
                total_checks += 1.0
                check = signal_map.get(rec.category.value)
                if check is not None and check(tc):
                    total_valid += 1.0
        return total_valid / total_checks if total_checks > 0 else 1.0

    def _check_evidence_integrity(
        self,
        corpus: list[RecommendationTestCase],
        results: dict[str, RecommendationSet],
    ) -> float:
        """Every recommendation has at least one evidence_id."""
        total = 0.0
        valid = 0.0
        for tc in corpus:
            result = results.get(tc.name)
            if result is None:
                continue
            for rec in result.recommendations:
                total += 1.0
                if len(rec.evidence_ids) > 0:
                    valid += 1.0
        return valid / total if total > 0 else 1.0

    def _check_priority_accuracy(
        self,
        corpus: list[RecommendationTestCase],
        results: dict[str, RecommendationSet],
    ) -> float:
        """Recommendations sorted by priority descending."""
        total = 0.0
        valid = 0.0
        for tc in corpus:
            result = results.get(tc.name)
            if result is None:
                continue
            recs = result.recommendations
            if len(recs) <= 1:
                total += 1.0
                valid += 1.0
                continue
            for i in range(len(recs) - 1):
                total += 1.0
                if recs[i].priority <= recs[i + 1].priority:
                    valid += 1.0
        return valid / total if total > 0 else 1.0

    def _check_determinism(
        self,
        corpus: list[RecommendationTestCase],
        results: dict[str, RecommendationSet],
        num_runs: int = 3,
    ) -> float:
        """Same inputs produce identical recommendation content across multiple runs.

        compiled_at is excluded — it is provenance metadata, not a recommendation property.
        Two RecommendationSets with different compiled_at but identical recommendations
        are considered deterministic.
        """
        if not corpus:
            return 1.0
        first_serialized: dict[str, list[dict]] = {}
        for name, result in results.items():
            first_serialized[name] = [
                {k: v for k, v in r.to_dict().items() if k != "compiled_at"}
                for r in result.recommendations
            ]

        for _ in range(num_runs - 1):
            for tc in corpus:
                result = self.engine.generate(
                    org_state=tc.org_state,
                    graph_state=tc.graph_state,
                    activity_state=tc.activity_state,
                )
                current = [
                    {k: v for k, v in r.to_dict().items() if k != "compiled_at"}
                    for r in result.recommendations
                ]
                if current != first_serialized.get(tc.name, []):
                    return 0.0
        return 1.0

    def _check_replayability(
        self,
        corpus: list[RecommendationTestCase],
        previous_results: dict[str, RecommendationSet] | None,
    ) -> float:
        """Idempotent: same inputs produce identical recommendations.

        compiled_at is excluded — it is provenance metadata.
        """
        if previous_results is None:
            return 1.0
        for tc in corpus:
            prev = previous_results.get(tc.name)
            if prev is None:
                continue
            current = self.engine.generate(
                org_state=tc.org_state,
                graph_state=tc.graph_state,
                activity_state=tc.activity_state,
            )
            prev_dicts = [
                {k: v for k, v in r.to_dict().items() if k != "compiled_at"}
                for r in prev.recommendations
            ]
            curr_dicts = [
                {k: v for k, v in r.to_dict().items() if k != "compiled_at"}
                for r in current.recommendations
            ]
            if prev_dicts != curr_dicts:
                return 0.0
        return 1.0


def check_recommendation_gates(
    result: RecommendationEvalResult,
    thresholds: EvaluationThresholds | None = None,
) -> tuple[bool, list[str]]:
    """Check if recommendation evaluation passes exit gates."""
    if thresholds is None:
        thresholds = EvaluationThresholds()
    return result.passes_exit_gate()
