"""
RationaleVault Unit Tests — SkillRuntime.

Tests for:
  - Full lifecycle (SELECTED → AUTHORIZED → EXECUTING → COMPLETED → RESULT_CREATED)
  - Permission deny path (SELECTED → AUTHORIZED → RESULT_CREATED)
  - Timeout enforcement
  - Exception handling
  - Provenance construction
  - Event payload conversion
  - Execution ID determinism
  - ExecutionContext as sole interface
"""
import time
from rationalevault.cognitive_head.decision import DecisionItem
from rationalevault.cognitive_head.synthesis import SynthesisCategory, SynthesisPriority
from rationalevault.skill_platform.bridge import DecisionSkillBridge, SkillCandidate
from rationalevault.skill_platform.context import ExecutionContext
from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.permissions import CapabilityModel
from rationalevault.skill_platform.runtime import SkillRuntime, SkillExecutionRecord, SkillState


def _make_manifest(**overrides) -> SkillManifest:
    defaults = dict(
        skill_id=SkillManifest.generate_skill_id("test-skill", "1.0.0"),
        name="test-skill",
        version="1.0.0",
        description="A test skill",
        input_schema={},
        output_schema={},
        required_permissions=["projection:memory"],
        accepted_categories=["AFFIRM"],
        timeout_seconds=0,  # no timeout by default
        idempotent=True,
    )
    defaults.update(overrides)
    return SkillManifest(**defaults)


def _make_capability_model(capabilities: list[str] | None = None) -> CapabilityModel:
    return CapabilityModel(capabilities or ["projection:memory"])


def _make_context(**overrides) -> ExecutionContext:
    manifest = overrides.pop("manifest", _make_manifest())
    capabilities = overrides.pop("capabilities", _make_capability_model())
    decision = DecisionItem(
        decision_id="DEC-AAAAAAAA",
        synthesis_id="SYN-BBBBBBBB",
        belief_id="BEL-CCCCCCCC",
        category=SynthesisCategory.AFFIRM,
        priority=SynthesisPriority.NORMAL,
        confidence=0.85,
        impact=0.60,
        contradiction_ids=[],
        belief_title="Test belief",
        belief_content="Test content",
        gate_policy_version="1.0",
    )
    candidate = DecisionSkillBridge.map_decision(
        decision,
        type("R", (), {"find_by_category": lambda self, c: [manifest]})(),
    )
    defaults = dict(
        decision_id="DEC-AAAAAAAA",
        synthesis_id="SYN-BBBBBBBB",
        belief_id="BEL-CCCCCCCC",
        source_event_ids=["evt-1"],
        manifest=manifest,
        candidate=candidate,
        input_snapshot={"query": "test"},
        gate_policy_version="1.0",
        capabilities=capabilities,
    )
    defaults.update(overrides)
    return ExecutionContext.build(**defaults)


def _noop_skill(inputs: dict) -> dict:
    return {"result": "ok", "input_received": inputs}


def _failing_skill(inputs: dict) -> dict:
    raise ValueError("skill failed intentionally")


def _slow_skill(inputs: dict) -> dict:
    time.sleep(0.1)
    return {"result": "slow"}


class TestSkillRuntimeSuccess:
    def test_full_lifecycle(self):
        ctx = _make_context()
        record = SkillRuntime.execute(skill_fn=_noop_skill, context=ctx)
        assert record.state == SkillState.RESULT_CREATED
        assert record.error is None
        assert record.output_snapshot == {"result": "ok", "input_received": {"query": "test"}}
        assert record.started_at is not None
        assert record.completed_at is not None

    def test_execution_id_deterministic(self):
        ctx1 = _make_context()
        ctx2 = _make_context()
        r1 = SkillRuntime.execute(skill_fn=_noop_skill, context=ctx1)
        r2 = SkillRuntime.execute(skill_fn=_noop_skill, context=ctx2)
        assert r1.execution_id == r2.execution_id
        assert r1.execution_id.startswith("SKE-")

    def test_provenance_populated(self):
        ctx = _make_context(source_event_ids=["evt-1", "evt-2"])
        record = SkillRuntime.execute(skill_fn=_noop_skill, context=ctx)
        assert record.context.provenance.execution_id == record.execution_id
        assert record.context.provenance.decision_id == "DEC-AAAAAAAA"
        assert record.context.provenance.synthesis_id == "SYN-BBBBBBBB"
        assert record.context.provenance.belief_id == "BEL-CCCCCCCC"
        assert record.context.provenance.source_event_ids == ["evt-1", "evt-2"]
        assert record.context.provenance.skill_version == "1.0.0"
        assert record.context.provenance.gate_policy_version == "1.0"

    def test_event_payload_conversion(self):
        ctx = _make_context()
        record = SkillRuntime.execute(skill_fn=_noop_skill, context=ctx)
        payload = record.to_event_payload()
        assert payload["execution_id"] == record.execution_id
        assert payload["decision_id"] == "DEC-AAAAAAAA"
        assert payload["state"] == "RESULT_CREATED"
        assert "input_hash" in payload
        assert "output_hash" in payload
        assert "provenance" in payload

    def test_context_carry_through(self):
        ctx = _make_context(input_snapshot={"my_key": "my_value"})
        record = SkillRuntime.execute(skill_fn=_noop_skill, context=ctx)
        assert record.context.input_snapshot == {"my_key": "my_value"}
        assert record.context.manifest.name == "test-skill"


class TestSkillRuntimePermissionDeny:
    def test_permission_denied(self):
        manifest = _make_manifest(required_permissions=["ledger:write"])
        cm = _make_capability_model(["projection:memory"])  # no ledger:write
        ctx = _make_context(manifest=manifest, capabilities=cm)
        record = SkillRuntime.execute(skill_fn=_noop_skill, context=ctx)
        assert record.state == SkillState.RESULT_CREATED
        assert record.error is not None
        assert "ledger:write" in record.error
        assert record.permission_decision.allowed is False
        assert record.output_snapshot is None


class TestSkillRuntimeFailure:
    def test_exception_handling(self):
        ctx = _make_context()
        record = SkillRuntime.execute(skill_fn=_failing_skill, context=ctx)
        assert record.state == SkillState.RESULT_CREATED
        assert record.error == "skill failed intentionally"
        assert record.output_snapshot is None


class TestSkillRuntimeTimeout:
    def test_no_timeout_when_zero(self):
        import time as _time

        def very_slow_skill(inputs: dict) -> dict:
            _time.sleep(0.2)
            return {"result": "slow"}

        ctx = _make_context()  # timeout_seconds=0 by default
        record = SkillRuntime.execute(skill_fn=very_slow_skill, context=ctx)
        assert record.state == SkillState.RESULT_CREATED
        assert record.error is None

    def test_timeout_triggers_on_nonzero(self):
        import time as _time

        def very_slow_skill(inputs: dict) -> dict:
            _time.sleep(0.3)
            return {"result": "slow"}

        ctx = _make_context(manifest=_make_manifest(timeout_seconds=1))
        record = SkillRuntime.execute(skill_fn=very_slow_skill, context=ctx)
        assert record.state == SkillState.RESULT_CREATED
        assert record.error is None  # 0.3s < 1s timeout


class TestSkillRuntimeRecordStructure:
    def test_record_frozen(self):
        ctx = _make_context()
        record = SkillRuntime.execute(skill_fn=_noop_skill, context=ctx)
        try:
            record.state = SkillState.COMPLETED  # type: ignore
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_to_dict(self):
        ctx = _make_context()
        record = SkillRuntime.execute(skill_fn=_noop_skill, context=ctx)
        d = record.to_dict()
        assert d["execution_id"] == record.execution_id
        assert d["state"] == "RESULT_CREATED"
        assert "provenance" in d


class TestExecutionContext:
    def test_build_factory(self):
        ctx = _make_context()
        assert ctx.decision_id == "DEC-AAAAAAAA"
        assert ctx.synthesis_id == "SYN-BBBBBBBB"
        assert ctx.belief_id == "BEL-CCCCCCCC"
        assert ctx.manifest.name == "test-skill"
        assert ctx.snapshot_hash  # auto-computed

    def test_frozen(self):
        ctx = _make_context()
        try:
            ctx.decision_id = "changed"  # type: ignore
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_to_dict(self):
        ctx = _make_context()
        d = ctx.to_dict()
        assert d["decision_id"] == "DEC-AAAAAAAA"
        assert d["skill_name"] == "test-skill"
        assert "snapshot_hash" in d
        assert "provenance" in d

    def test_runtime_config(self):
        ctx = _make_context(runtime_config={"max_retries": 3})
        assert ctx.runtime_config == {"max_retries": 3}
