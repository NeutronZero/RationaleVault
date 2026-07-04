"""
RationaleVault Unit Tests — SkillInput & SkillOutput.
"""
from rationalevault.skill_platform.skill_input import SkillInput, ProjectionSnapshot
from rationalevault.skill_platform.skill_output import SkillOutput


class TestSkillInput:
    def test_deterministic_hash(self):
        i1 = SkillInput(decision_id="DEC-1", belief_title="test", confidence=0.8)
        i2 = SkillInput(decision_id="DEC-1", belief_title="test", confidence=0.8)
        assert i1.input_hash == i2.input_hash
        assert len(i1.input_hash) == 16

    def test_different_input_different_hash(self):
        i1 = SkillInput(decision_id="DEC-1", confidence=0.8)
        i2 = SkillInput(decision_id="DEC-2", confidence=0.8)
        assert i1.input_hash != i2.input_hash

    def test_frozen(self):
        i = SkillInput(decision_id="DEC-1")
        try:
            i.decision_id = "changed"  # type: ignore
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_to_dict(self):
        i = SkillInput(decision_id="DEC-1", belief_title="test", confidence=0.8)
        d = i.to_dict()
        assert d["decision_id"] == "DEC-1"
        assert d["belief_title"] == "test"
        assert d["input_hash"] == i.input_hash

    def test_version(self):
        i = SkillInput()
        assert i.version == "1.0"


class TestProjectionSnapshot:
    def test_empty(self):
        ps = ProjectionSnapshot()
        d = ps.to_dict()
        assert d == {"memory": {}, "knowledge": {}, "execution_state": {}, "graph": {}, "context": {}}

    def test_with_data(self):
        ps = ProjectionSnapshot(memory={"key": "value"})
        assert ps.memory == {"key": "value"}


class TestSkillOutput:
    def test_deterministic_hash(self):
        o1 = SkillOutput(status="completed", summary="test")
        o2 = SkillOutput(status="completed", summary="test")
        assert o1.output_hash == o2.output_hash

    def test_different_output_different_hash(self):
        o1 = SkillOutput(status="completed", summary="a")
        o2 = SkillOutput(status="completed", summary="b")
        assert o1.output_hash != o2.output_hash

    def test_to_dict(self):
        o = SkillOutput(status="completed", summary="test", confirmed_items=["item1"])
        d = o.to_dict()
        assert d["status"] == "completed"
        assert d["confirmed_items"] == ["item1"]

    def test_from_dict_round_trip(self):
        o = SkillOutput(status="completed", summary="test", metrics={"dur": 100})
        d = o.to_dict()
        o2 = SkillOutput.from_dict(d)
        assert o2.status == o.status
        assert o2.summary == o.summary
        assert o2.metrics == o.metrics

    def test_frozen(self):
        o = SkillOutput(status="completed")
        try:
            o.status = "failed"  # type: ignore
            assert False, "Should be frozen"
        except AttributeError:
            pass
