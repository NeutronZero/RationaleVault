"""
RationaleVault Unit Tests — SkillInputBuilder.
"""
from rationalevault.cognitive_head.decision import DecisionItem
from rationalevault.cognitive_head.synthesis import SynthesisCategory, SynthesisPriority
from rationalevault.skill_platform.input_builder import SkillInputBuilder
from rationalevault.skill_platform.skill_input import ProjectionSnapshot


def _make_decision(**overrides) -> DecisionItem:
    defaults = dict(
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
    defaults.update(overrides)
    return DecisionItem(**defaults)


class TestSkillInputBuilder:
    def test_build_from_decision(self):
        d = _make_decision()
        si = SkillInputBuilder.build(d)
        assert si.decision_id == "DEC-AAAAAAAA"
        assert si.belief_title == "Test belief"
        assert si.confidence == 0.85
        assert si.category == "AFFIRM"

    def test_build_with_projections(self):
        d = _make_decision()
        ps = ProjectionSnapshot(memory={"key": "value"})
        si = SkillInputBuilder.build(d, projections=ps)
        assert si.projections.memory == {"key": "value"}

    def test_build_with_metadata(self):
        d = _make_decision()
        si = SkillInputBuilder.build(d, metadata={"custom": "data"})
        assert si.metadata == {"custom": "data"}

    def test_build_with_snapshots(self):
        d = _make_decision()
        si = SkillInputBuilder.build_with_snapshots(
            d, memory={"m": 1}, knowledge={"k": 2}
        )
        assert si.projections.memory == {"m": 1}
        assert si.projections.knowledge == {"k": 2}

    def test_deterministic_hash(self):
        d = _make_decision()
        si1 = SkillInputBuilder.build(d)
        si2 = SkillInputBuilder.build(d)
        assert si1.input_hash == si2.input_hash
