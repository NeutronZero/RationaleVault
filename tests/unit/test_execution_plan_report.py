"""
RationaleVault Unit Tests — ExecutionPlan & ExecutionReport.
"""
from rationalevault.skill_platform.execution_plan import ExecutionPlan
from rationalevault.skill_platform.execution_report import ExecutionReport
from rationalevault.skill_platform.result import SkillResult, SkillResultStatus
from rationalevault.skill_platform.provenance import Provenance


def _make_result(status: SkillResultStatus = SkillResultStatus.COMPLETED) -> SkillResult:
    prov = Provenance(
        execution_id="SKE-AAAAAAAA", decision_id="DEC-BBBBBBBB",
        synthesis_id="SYN-CCCCCCCC", belief_id="BEL-DDDDDDDD",
        source_event_ids=[], skill_version="1.0.0", gate_policy_version="1.0",
        input_snapshot_hash="HASH", timestamp="2026-01-01T00:00:00Z",
    )
    if status == SkillResultStatus.COMPLETED:
        return SkillResult.success(
            execution_id="SKE-AAAAAAAA", decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111", outputs={"key": "value"},
            artifacts=[], metrics={"duration_ms": 100}, warnings=[],
            duration_ms=100, provenance=prov,
        )
    else:
        return SkillResult.failure(
            execution_id="SKE-AAAAAAAA", decision_id="DEC-BBBBBBBB",
            skill_id="SKL-11111111", error="failed", duration_ms=50,
            provenance=prov, status=status,
        )


class TestExecutionReport:
    def test_from_results(self):
        results = [_make_result(), _make_result()]
        report = ExecutionReport.from_results(results)
        assert report.total_executions == 2
        assert report.total_completed == 2
        assert report.total_failed == 0

    def test_from_results_with_failures(self):
        results = [
            _make_result(SkillResultStatus.COMPLETED),
            _make_result(SkillResultStatus.FAILED),
        ]
        report = ExecutionReport.from_results(results)
        assert report.total_completed == 1
        assert report.total_failed == 1
        assert len(report.failures) == 1

    def test_to_dict(self):
        report = ExecutionReport.from_results([_make_result()])
        d = report.to_dict()
        assert d["total_executions"] == 1
        assert "results" in d

    def test_summary(self):
        report = ExecutionReport.from_results([_make_result()])
        assert "1 total" in report.summary
