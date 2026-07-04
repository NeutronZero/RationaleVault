"""
RationaleVault Unit Tests — Phase C3 (Artifacts, Gates, and Evaluation).
"""
import pytest
from rationalevault.skill_platform.artifact import (
    Artifact,
    ArtifactCandidate,
    ArtifactKind,
    ArtifactLineage,
    ArtifactReference,
)
from rationalevault.skill_platform.gate import (
    ExecutionGate,
    ExecutionGatePolicy,
    ExecutionPromoter,
    GateRule,
    PromotionDecisionType,
    SuccessRateRule,
    GateResult,
)
from rationalevault.skill_platform.execution_state import ExecutionState, ExecutionEntry
from rationalevault.skill_platform.execution_report import ExecutionReport
from rationalevault.evaluation.thresholds import ExecutionThresholds
from rationalevault.evaluation.execution_evaluator import ExecutionEvaluator, ExecutionEvaluationInput


def test_artifact_contracts() -> None:
    # 1. References
    ref = ArtifactReference(scheme="file", location="reports/summary.md")
    d = ref.to_dict()
    assert d["scheme"] == "file"
    assert d["location"] == "reports/summary.md"
    assert ArtifactReference.from_dict(d) == ref

    # 2. Artifact stable ID generation
    art_id = Artifact.generate_artifact_id("SKL-12345678", "SKE-87654321", "CONTENTHASH")
    assert art_id.startswith("ART-")

    # 3. Artifact serialization
    art = Artifact(
        artifact_id=art_id,
        kind=ArtifactKind.MARKDOWN,
        reference=ref,
        hash="CONTENTHASH",
        size=128,
        mime_type="text/markdown",
        created_at="2026-01-01T00:00:00Z",
    )
    art_dict = art.to_dict()
    assert art_dict["artifact_id"] == art_id
    assert art_dict["kind"] == "MARKDOWN"
    assert Artifact.from_dict(art_dict) == art


def test_gate_rules_and_evaluation() -> None:
    # Build a mock state with 1 failure out of 10 runs (90% success rate)
    entry_ok = ExecutionEntry(
        execution_id="SKE-1", decision_id="DEC-1", skill_id="SKL-1",
        state="COMPLETED", input_hash="X", output_hash="Y",
        error=None, started_at=None, completed_at=None, duration_ms=100,
    )
    entry_fail = ExecutionEntry(
        execution_id="SKE-2", decision_id="DEC-2", skill_id="SKL-1",
        state="FAILED", input_hash="X", output_hash="Y",
        error="Oops", started_at=None, completed_at=None, duration_ms=150,
    )

    state = ExecutionState(
        pending_decisions=[],
        completed_executions=[entry_ok] * 9,
        failed_executions=[entry_fail],
        timeout_executions=[],
        denied_executions=[],
        execution_counts={"SKL-1": 10},
        success_counts={"SKL-1": 9},
        durations={"SKL-1": [100] * 9 + [150]},
        total_executions=10,
        total_completed=9,
        total_failed=1,
        total_timeout=0,
        total_denied=0,
    )

    report = ExecutionReport.from_results([])
    thresholds = ExecutionThresholds(
        profile_name="production",
        min_success_rate=0.95,  # Needs 95% success
        max_timeout_rate=0.05,
        max_denial_rate=0.05,
        min_overall_score=0.95,
    )

    # Evaluate
    evaluator = ExecutionEvaluator()
    evaluation = evaluator.evaluate(
        ExecutionEvaluationInput(state=state, report=report, thresholds=thresholds)
    )

    assert evaluation.success_rate == 0.90
    assert not evaluation.passed  # Failed because 90% < 95%

    # Apply Gate Policy
    policy = ExecutionGatePolicy(min_success_rate=0.85, min_overall_score=0.80)
    gate_result = ExecutionGate.evaluate(evaluation, policy)
    assert gate_result.decision == PromotionDecisionType.PASS  # Passes because 90% >= 85%

    # Apply Promoting
    cand = ArtifactCandidate(
        candidate_id="ACAND-1",
        kind=ArtifactKind.MARKDOWN,
        reference=ArtifactReference("file", "run.md"),
        hash="HASH",
        size=10,
        mime_type="text/markdown",
    )
    promotion = ExecutionPromoter.promote(gate_result, [cand], "1.0")
    assert promotion.decision == PromotionDecisionType.PASS
    assert len(promotion.artifact_ids) == 1
    assert promotion.artifact_ids[0].startswith("ART-")


def test_custom_gate_rule() -> None:
    class AlwaysFailRule(GateRule):
        def evaluate(self, evaluation, policy):
            return False, "Failed by design"

    # Evaluate with default policy (which passes)
    policy = ExecutionGatePolicy(min_success_rate=0.50, min_overall_score=0.50)
    evaluator = ExecutionEvaluator()
    thresholds = ExecutionThresholds(min_success_rate=0.50, min_overall_score=0.50)
    
    empty_state = ExecutionState(
        pending_decisions=[], completed_executions=[], failed_executions=[],
        timeout_executions=[], denied_executions=[], execution_counts={},
        success_counts={}, durations={}, total_executions=0,
        total_completed=0, total_failed=0, total_timeout=0, total_denied=0,
    )
    evaluation = evaluator.evaluate(
        ExecutionEvaluationInput(state=empty_state, report=ExecutionReport(), thresholds=thresholds)
    )

    # Validate gate result is PASS normally
    gate_result_ok = ExecutionGate.evaluate(evaluation, policy)
    assert gate_result_ok.decision == PromotionDecisionType.PASS

    # Injecting custom fail rule forces BLOCK
    gate_result_fail = ExecutionGate.evaluate(evaluation, policy, rules=[AlwaysFailRule()])
    assert gate_result_fail.decision == PromotionDecisionType.BLOCK
    assert "Failed by design" in gate_result_fail.violations


def test_artifact_promotion_report() -> None:
    from rationalevault.skill_platform.gate import ArtifactPromotionReport

    policy = ExecutionGatePolicy(min_success_rate=0.50, min_overall_score=0.50)
    evaluator = ExecutionEvaluator()
    thresholds = ExecutionThresholds(min_success_rate=0.50, min_overall_score=0.50)
    empty_state = ExecutionState(
        pending_decisions=[], completed_executions=[], failed_executions=[],
        timeout_executions=[], denied_executions=[], execution_counts={},
        success_counts={}, durations={}, total_executions=0,
        total_completed=0, total_failed=0, total_timeout=0, total_denied=0,
    )
    evaluation = evaluator.evaluate(
        ExecutionEvaluationInput(state=empty_state, report=ExecutionReport(), thresholds=thresholds)
    )
    gate_result = ExecutionGate.evaluate(evaluation, policy)
    cand = ArtifactCandidate(
        candidate_id="ACAND-1",
        kind=ArtifactKind.MARKDOWN,
        reference=ArtifactReference("file", "run.md"),
        hash="HASH",
        size=10,
        mime_type="text/markdown",
    )
    promotion = ExecutionPromoter.promote(gate_result, [cand], "1.0")

    # Build promoted artifact
    art = Artifact(
        artifact_id="ART-1",
        kind=cand.kind,
        reference=cand.reference,
        hash=cand.hash,
        size=cand.size,
        mime_type=cand.mime_type,
        created_at="2026-01-01T00:00:00Z",
    )

    # 1. Successful promotion report (where candidate is promoted)
    report_ok = ArtifactPromotionReport(
        promoted=[art],
        rejected=[],
        decision=promotion,
        gate_result=gate_result,
        evaluation=evaluation,
    )
    assert report_ok.promoted == [art]
    assert report_ok.rejected == []

    d = report_ok.to_dict()
    assert d["version"] == "1.0"
    assert len(d["promoted"]) == 1
    assert len(d["rejected"]) == 0

    reconstructed = ArtifactPromotionReport.from_dict(d)
    assert reconstructed.promoted[0].artifact_id == "ART-1"
    assert reconstructed.promoted[0].hash == "HASH"

    # 2. Blocked promotion report (where candidate is rejected)
    promotion_blocked = ExecutionPromoter.promote(
        GateResult(decision=PromotionDecisionType.BLOCK, violations=["error"], warnings=[], evaluated_policy_version="1.0"),
        [cand],
        "1.0"
    )
    report_blocked = ArtifactPromotionReport(
        promoted=[],
        rejected=[cand],
        decision=promotion_blocked,
        gate_result=gate_result,
        evaluation=evaluation,
    )
    assert report_blocked.promoted == []
    assert report_blocked.rejected == [cand]

