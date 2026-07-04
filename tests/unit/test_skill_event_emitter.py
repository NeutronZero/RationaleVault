"""
RationaleVault Unit Tests — SkillEventEmitter & ExecutionSummary.
"""
from rationalevault.skill_platform.event_emitter import SkillEventEmitter, ExecutionSummary
from rationalevault.skill_platform.provenance import Provenance


def _make_summary(**overrides) -> ExecutionSummary:
    prov = Provenance(
        execution_id="SKE-AAAAAAAA",
        decision_id="DEC-BBBBBBBB",
        synthesis_id="SYN-CCCCCCCC",
        belief_id="BEL-DDDDDDDD",
        source_event_ids=["evt-1"],
        skill_version="1.0.0",
        gate_policy_version="1.0",
        input_snapshot_hash="HASH",
        timestamp="2026-01-01T00:00:00Z",
    )
    defaults = dict(
        execution_id="SKE-AAAAAAAA",
        decision_id="DEC-BBBBBBBB",
        skill_id="SKL-11111111",
        skill_name="test-skill",
        skill_version="1.0.0",
        state="COMPLETED",
        input_hash="INHASH",
        output_hash="OUTHASH",
        error=None,
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
        duration_ms=100,
        provenance=prov,
        timeout_seconds=30,
    )
    defaults.update(overrides)
    return ExecutionSummary(**defaults)


class TestSkillEventEmitter:
    def test_emit_produces_event(self):
        s = _make_summary()
        event = SkillEventEmitter.emit(s)
        assert event.execution_id == "SKE-AAAAAAAA"
        assert event.state == "COMPLETED"
        assert event.event_type == "SKILL_EXECUTED"

    def test_event_payload(self):
        s = _make_summary()
        event = SkillEventEmitter.emit(s)
        payload = event.to_payload()
        assert payload["execution_id"] == "SKE-AAAAAAAA"
        assert payload["state"] == "COMPLETED"
        assert "provenance" in payload

    def test_event_frozen(self):
        s = _make_summary()
        event = SkillEventEmitter.emit(s)
        try:
            event.state = "FAILED"  # type: ignore
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_from_record(self):
        from rationalevault.skill_platform.runtime import SkillExecutionRecord, SkillState
        from rationalevault.skill_platform.context import ExecutionContext
        from rationalevault.skill_platform.bridge import SkillCandidate
        from rationalevault.cognitive_head.decision import DecisionItem
        from rationalevault.cognitive_head.synthesis import SynthesisCategory, SynthesisPriority
        from rationalevault.skill_platform.permissions import CapabilityModel, PermissionDecision
        from rationalevault.skill_platform.manifest import SkillManifest

        d = DecisionItem(
            decision_id="DEC-AAAAAAAA", synthesis_id="SYN-BBBBBBBB",
            belief_id="BEL-CCCCCCCC", category=SynthesisCategory.AFFIRM,
            priority=SynthesisPriority.NORMAL, confidence=0.85, impact=0.60,
            contradiction_ids=[], belief_title="test", belief_content="test",
            gate_policy_version="1.0",
        )
        m = _make_summary()
        manifest = SkillManifest(
            skill_id=SkillManifest.generate_skill_id("test", "1.0.0"),
            name="test", version="1.0.0", description="test",
            input_schema={}, output_schema={}, required_permissions=[],
            accepted_categories=[], timeout_seconds=30, idempotent=True,
        )
        ctx = ExecutionContext(
            decision_id="DEC-AAAAAAAA", synthesis_id="SYN-BBBBBBBB",
            belief_id="BEL-CCCCCCCC", source_event_ids=[],
            manifest=manifest, candidate=SkillCandidate(
                decision=d, manifest=manifest, match_score=1.0,
                blocked=False, blocked_reason="", specificity=1,
            ),
            input_snapshot={}, provenance=m.provenance,
            capabilities=CapabilityModel(), gate_policy_version="1.0",
        )
        record = SkillExecutionRecord(
            execution_id="SKE-AAAAAAAA", state=SkillState.RESULT_CREATED,
            context=ctx, output_snapshot=None, error=None,
            started_at="2026-01-01T00:00:00Z", completed_at="2026-01-01T00:00:01Z",
            permission_decision=PermissionDecision(allowed=True, missing_capabilities=[], denial_reason="", evaluation_version="1.0"),
            timeout_seconds=30,
        )
        summary = SkillEventEmitter.from_record(record)
        assert summary.execution_id == "SKE-AAAAAAAA"
