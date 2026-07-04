"""
RationaleVault Unit Tests — SkillResolver & SkillActivator.
"""
from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.resolver import SkillResolver, SkillDescriptor, ActivationTarget
from rationalevault.skill_platform.activator import SkillActivator, SkillActivationError


def _make_manifest(name: str = "affirm-skill") -> SkillManifest:
    return SkillManifest(
        skill_id=SkillManifest.generate_skill_id(name, "1.0.0"),
        name=name,
        version="1.0.0",
        description="test",
        input_schema={},
        output_schema={},
        required_permissions=[],
        accepted_categories=[],
        timeout_seconds=30,
        idempotent=True,
    )


class TestSkillResolver:
    def test_resolve_builtin(self):
        m = _make_manifest("affirm-skill")
        d = SkillResolver.resolve(m)
        assert d.name == "affirm-skill"
        assert d.activation_target.module_path == "rationalevault.skills.affirm_skill"
        assert d.activation_target.class_name == "AffirmSkill"

    def test_resolve_unknown(self):
        m = _make_manifest("unknown-skill")
        d = SkillResolver.resolve(m)
        assert d.name == "unknown-skill"

    def test_descriptor_to_dict(self):
        m = _make_manifest("affirm-skill")
        d = SkillResolver.resolve(m)
        dd = d.to_dict()
        assert dd["name"] == "affirm-skill"
        assert "activation_target" in dd


class TestSkillActivator:
    def test_activate_builtin(self):
        m = _make_manifest("affirm-skill")
        d = SkillResolver.resolve(m)
        fn = SkillActivator.activate(d)
        assert callable(fn)

    def test_activate_unknown_raises(self):
        d = SkillDescriptor(
            skill_id="SKL-00000000",
            name="nonexistent",
            version="1.0.0",
            activation_target=ActivationTarget(
                module_path="rationalevault.skills.nonexistent_skill",
                class_name="NonexistentSkill",
            ),
            required_permissions=[],
            accepted_categories=[],
        )
        try:
            SkillActivator.activate(d)
            assert False, "Should have raised SkillActivationError"
        except SkillActivationError as e:
            assert "Cannot import" in str(e)

    def test_activation_target_to_dict(self):
        t = ActivationTarget(module_path="mod.path", class_name="ClassName")
        d = t.to_dict()
        assert d["module_path"] == "mod.path"
        assert d["class_name"] == "ClassName"
