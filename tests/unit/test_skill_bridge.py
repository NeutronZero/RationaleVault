"""
RationaleVault Unit Tests — Decision→Skill Bridge.

Tests for:
  - SkillCandidate structure
  - DecisionSkillBridge.map_decision (matched and blocked paths)
  - Specificity ranking (fewer accepted_categories = more specific)
  - DecisionSkillBridge.map_decision_set preserves order
"""
from rationalevault.cognitive_head.decision import DecisionItem, DecisionSet
from rationalevault.cognitive_head.synthesis import SynthesisCategory, SynthesisPriority
from rationalevault.skill_platform.bridge import DecisionSkillBridge, SkillCandidate
from rationalevault.skill_platform.manifest import SkillManifest, SkillManifestRegistry


def _make_decision(category: str = "AFFIRM", **overrides) -> DecisionItem:
    defaults = dict(
        decision_id="DEC-AAAAAAAA",
        synthesis_id="SYN-BBBBBBBB",
        belief_id="BEL-CCCCCCCC",
        category=SynthesisCategory(category),
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


def _make_manifest(name: str = "test-skill", categories: list[str] | None = None, **overrides) -> SkillManifest:
    cats = categories or ["AFFIRM", "CHALLENGE"]
    defaults = dict(
        skill_id=SkillManifest.generate_skill_id(name, "1.0.0"),
        name=name,
        version="1.0.0",
        description=f"Skill {name}",
        input_schema={},
        output_schema={},
        required_permissions=[],
        accepted_categories=cats,
        timeout_seconds=30,
        idempotent=True,
    )
    defaults.update(overrides)
    return SkillManifest(**defaults)


class TestSkillCandidate:
    def test_structure(self):
        d = _make_decision()
        m = _make_manifest()
        sc = SkillCandidate(
            decision=d,
            manifest=m,
            match_score=1.0,
            blocked=False,
            blocked_reason="",
            specificity=2,
        )
        assert sc.decision == d
        assert sc.manifest == m
        assert sc.match_score == 1.0
        assert sc.blocked is False

    def test_to_dict(self):
        d = _make_decision()
        m = _make_manifest()
        sc = SkillCandidate(
            decision=d,
            manifest=m,
            match_score=1.0,
            blocked=False,
            blocked_reason="",
            specificity=2,
        )
        dd = sc.to_dict()
        assert dd["decision_id"] == d.decision_id
        assert dd["skill_id"] == m.skill_id
        assert dd["blocked"] is False


class TestDecisionSkillBridge:
    def test_match_single_skill(self):
        reg = SkillManifestRegistry()
        m = _make_manifest(categories=["AFFIRM"])
        reg.register(m)
        d = _make_decision(category="AFFIRM")
        sc = DecisionSkillBridge.map_decision(d, reg)
        assert sc.blocked is False
        assert sc.manifest.skill_id == m.skill_id
        assert sc.match_score == 1.0

    def test_no_match_blocked(self):
        reg = SkillManifestRegistry()
        m = _make_manifest(categories=["MONITOR"])
        reg.register(m)
        d = _make_decision(category="AFFIRM")
        sc = DecisionSkillBridge.map_decision(d, reg)
        assert sc.blocked is True
        assert sc.blocked_reason == "no_matching_skill"

    def test_specificity_ranking(self):
        reg = SkillManifestRegistry()
        broad = _make_manifest(
            name="broad-skill",
            categories=["AFFIRM", "CHALLENGE", "MONITOR"],
        )
        specific = _make_manifest(
            name="specific-skill",
            categories=["AFFIRM"],
        )
        reg.register(broad)
        reg.register(specific)
        d = _make_decision(category="AFFIRM")
        sc = DecisionSkillBridge.map_decision(d, reg)
        # Specific skill should be selected (fewer categories)
        assert sc.manifest.name == "specific-skill"
        assert sc.specificity == 1

    def test_deterministic_tiebreak(self):
        reg = SkillManifestRegistry()
        m1 = _make_manifest(name="aaa-skill", categories=["AFFIRM"])
        m2 = _make_manifest(name="zzz-skill", categories=["AFFIRM"])
        reg.register(m1)
        reg.register(m2)
        d = _make_decision(category="AFFIRM")
        sc = DecisionSkillBridge.map_decision(d, reg)
        # Both have specificity 1, tie broken by skill_id (alphabetical)
        assert sc.manifest.name == "aaa-skill"

    def test_map_decision_set_preserves_order(self):
        reg = SkillManifestRegistry()
        m = _make_manifest(categories=["AFFIRM", "CHALLENGE"])
        reg.register(m)
        d1 = _make_decision(category="AFFIRM", decision_id="DEC-11111111")
        d2 = _make_decision(category="CHALLENGE", decision_id="DEC-22222222")
        ds = DecisionSet(
            decisions=[d1, d2],
            blocked=[],
            gate_policy={"version": "1.0"},
            summary={"approved": 2, "blocked": 0},
        )
        candidates = DecisionSkillBridge.map_decision_set(ds, reg)
        assert len(candidates) == 2
        assert candidates[0].decision.decision_id == "DEC-11111111"
        assert candidates[1].decision.decision_id == "DEC-22222222"

    def test_empty_registry_blocks_all(self):
        reg = SkillManifestRegistry()
        d = _make_decision()
        sc = DecisionSkillBridge.map_decision(d, reg)
        assert sc.blocked is True
