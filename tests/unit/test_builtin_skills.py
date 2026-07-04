"""
RationaleVault Unit Tests — Built-in Skills.
"""
from rationalevault.skill_platform.skill_input import SkillInput
from rationalevault.skills.affirm_skill import AffirmSkill
from rationalevault.skills.challenge_skill import ChallengeSkill
from rationalevault.skills.resolve_skill import ResolveSkill
from rationalevault.skills.monitor_skill import MonitorSkill
from rationalevault.skills.builtin_registry import BuiltinSkillRegistry, create_builtin_registry


def _make_input(category: str = "AFFIRM") -> SkillInput:
    return SkillInput(
        decision_id="DEC-AAAAAAAA",
        belief_id="BEL-CCCCCCCC",
        belief_title="Test belief",
        belief_content="Test content",
        confidence=0.85,
        category=category,
    )


class TestAffirmSkill:
    def test_manifest(self):
        s = AffirmSkill()
        m = s.manifest()
        assert m.name == "affirm-skill"
        assert "AFFIRM" in m.accepted_categories

    def test_execute(self):
        s = AffirmSkill()
        out = s(_make_input("AFFIRM"))
        assert out.status == "completed"
        assert len(out.confirmed_items) == 1
        assert "Test belief" in out.confirmed_items[0]

    def test_capability_metadata(self):
        assert AffirmSkill.deterministic is True
        assert AffirmSkill.side_effect_free is True
        assert AffirmSkill.idempotent is True
        assert AffirmSkill.requires_network is False


class TestChallengeSkill:
    def test_execute(self):
        s = ChallengeSkill()
        out = s(_make_input("CHALLENGE"))
        assert out.status == "completed"
        assert len(out.challenged_items) == 1


class TestResolveSkill:
    def test_execute(self):
        s = ResolveSkill()
        out = s(_make_input("RESOLVE"))
        assert out.status == "completed"
        assert len(out.recommendations) > 0


class TestMonitorSkill:
    def test_execute(self):
        s = MonitorSkill()
        out = s(_make_input("MONITOR"))
        assert out.status == "completed"
        assert len(out.recommendations) > 0


class TestBuiltinSkillRegistry:
    def test_create_builtin_registry(self):
        reg = create_builtin_registry()
        assert len(reg) == 4

    def test_get_by_name(self):
        reg = create_builtin_registry()
        entry = reg.get("affirm-skill")
        assert entry is not None
        assert entry.manifest.name == "affirm-skill"

    def test_find_by_category(self):
        reg = create_builtin_registry()
        entries = reg.find_by_category("AFFIRM")
        assert len(entries) == 1

    def test_list_all(self):
        reg = create_builtin_registry()
        all_skills = reg.list_all()
        assert len(all_skills) == 4

    def test_contains(self):
        reg = create_builtin_registry()
        assert "affirm-skill" in reg
        assert "nonexistent" not in reg
