from __future__ import annotations

from rationalevault.evaluation.continuity_metrics import resolve_decision_state, compute_metrics, IdentityStatus, SemanticStatus, DecisionIntegrityState


def test_resolve_decision_state_preserved() -> None:
    expected = "Use SQLite as default"
    observed = ["Use SQLite as default"]
    ident, sem, state, obs = resolve_decision_state(expected, observed)
    assert ident == IdentityStatus.PRESERVED
    assert sem == SemanticStatus.CONSISTENT
    assert state == DecisionIntegrityState.HEALTHY
    assert obs == expected


def test_resolve_decision_state_contradicted() -> None:
    expected = "Use SQLite database"
    observed = ["Use PostgreSQL database"]
    ident, sem, state, obs = resolve_decision_state(expected, observed)
    assert sem == SemanticStatus.CONTRADICTED
    assert state == DecisionIntegrityState.CONTRADICTED


def test_weighted_metrics() -> None:
    expected_decisions = [
        {"decision": "Use SQLite", "severity": "critical"},
        {"decision": "Write unit tests", "severity": "low"}
    ]
    observed = ["Use PostgreSQL", "Write unit tests"]
    metrics = compute_metrics(
        expected_goal="Test",
        observed_goal="Test",
        expected_tasks=[],
        observed_tasks=[],
        expected_decisions=expected_decisions,
        observed_decisions=observed,
        expected_questions=[],
        observed_questions=[],
        expected_blockers=[],
        observed_blockers=[],
        expected_next_action="Done",
        observed_next_action="Done",
    )
    # The critical decision is contradicted (weight 5.0, score 0.0)
    # The low decision is preserved (weight 1.0, score 1.0)
    # Weighted integrity should be 1.0 / 6.0 = 0.1666
    assert abs(metrics.weighted_decision_integrity - 0.1666) < 0.01
    assert metrics.decision_contradiction_rate == 0.5
    # Weighted contradiction should be 5.0 / 6.0 = 0.8333
    assert abs(metrics.weighted_contradiction_rate - 0.8333) < 0.01
