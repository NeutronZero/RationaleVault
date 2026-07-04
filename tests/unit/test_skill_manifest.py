"""
RationaleVault Unit Tests — Skill Manifest & Registry.

Tests for:
  - SkillManifest ID determinism
  - SkillManifest to_dict / from_dict round-trip
  - SkillManifestRegistry add / get / list / find_by_category
  - Duplicate registration error
"""
from rationalevault.skill_platform.manifest import SkillManifest, SkillManifestRegistry


def _make_manifest(**overrides) -> SkillManifest:
    defaults = dict(
        skill_id=SkillManifest.generate_skill_id("test-skill", "1.0.0"),
        name="test-skill",
        version="1.0.0",
        description="A test skill",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
        required_permissions=["projection:memory"],
        accepted_categories=["AFFIRM", "CHALLENGE"],
        timeout_seconds=30,
        idempotent=True,
    )
    defaults.update(overrides)
    return SkillManifest(**defaults)


class TestSkillManifestID:
    def test_deterministic_id(self):
        id1 = SkillManifest.generate_skill_id("my-skill", "1.0.0")
        id2 = SkillManifest.generate_skill_id("my-skill", "1.0.0")
        assert id1 == id2
        assert id1.startswith("SKL-")
        assert len(id1) == 12  # SKL- + 8 hex chars

    def test_different_name_different_id(self):
        id1 = SkillManifest.generate_skill_id("skill-a", "1.0.0")
        id2 = SkillManifest.generate_skill_id("skill-b", "1.0.0")
        assert id1 != id2

    def test_different_version_different_id(self):
        id1 = SkillManifest.generate_skill_id("my-skill", "1.0.0")
        id2 = SkillManifest.generate_skill_id("my-skill", "1.0.1")
        assert id1 != id2

    def test_id_format(self):
        sid = SkillManifest.generate_skill_id("x", "0.1.0")
        assert sid.startswith("SKL-")
        hex_part = sid[4:]
        assert len(hex_part) == 8
        assert all(c in "0123456789ABCDEF" for c in hex_part)


class TestSkillManifestSerialisation:
    def test_to_dict_contains_all_fields(self):
        m = _make_manifest()
        d = m.to_dict()
        assert d["skill_id"] == m.skill_id
        assert d["name"] == "test-skill"
        assert d["version"] == "1.0.0"
        assert d["description"] == "A test skill"
        assert d["required_permissions"] == ["projection:memory"]
        assert d["accepted_categories"] == ["AFFIRM", "CHALLENGE"]
        assert d["timeout_seconds"] == 30
        assert d["idempotent"] is True

    def test_from_dict_round_trip(self):
        m = _make_manifest()
        d = m.to_dict()
        m2 = SkillManifest.from_dict(d)
        assert m2.skill_id == m.skill_id
        assert m2.name == m.name
        assert m2.version == m.version
        assert m2.required_permissions == m.required_permissions
        assert m2.accepted_categories == m.accepted_categories

    def test_frozen(self):
        m = _make_manifest()
        try:
            m.name = "changed"  # type: ignore
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestSkillManifestRegistry:
    def test_register_and_get(self):
        reg = SkillManifestRegistry()
        m = _make_manifest()
        reg.register(m)
        assert reg.get(m.skill_id) == m

    def test_get_by_name(self):
        reg = SkillManifestRegistry()
        m = _make_manifest()
        reg.register(m)
        assert reg.get_by_name("test-skill") == m

    def test_list_all(self):
        reg = SkillManifestRegistry()
        m1 = _make_manifest(name="skill-a", version="1.0.0")
        m2 = _make_manifest(name="skill-b", version="1.0.0")
        # Need different IDs for different names
        m2 = SkillManifest(
            skill_id=SkillManifest.generate_skill_id("skill-b", "1.0.0"),
            name="skill-b",
            version="1.0.0",
            description="B",
            input_schema={},
            output_schema={},
            required_permissions=[],
            accepted_categories=[],
            timeout_seconds=0,
            idempotent=False,
        )
        reg.register(m1)
        reg.register(m2)
        assert len(reg.list_all()) == 2

    def test_find_by_category(self):
        reg = SkillManifestRegistry()
        m = _make_manifest(accepted_categories=["AFFIRM", "MONITOR"])
        reg.register(m)
        assert len(reg.find_by_category("AFFIRM")) == 1
        assert len(reg.find_by_category("CHALLENGE")) == 0

    def test_duplicate_registration_error(self):
        reg = SkillManifestRegistry()
        m = _make_manifest()
        reg.register(m)
        try:
            reg.register(m)
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "already registered" in str(e)

    def test_len_and_contains(self):
        reg = SkillManifestRegistry()
        m = _make_manifest()
        assert len(reg) == 0
        assert m.skill_id not in reg
        reg.register(m)
        assert len(reg) == 1
        assert m.skill_id in reg

    def test_get_nonexistent_returns_none(self):
        reg = SkillManifestRegistry()
        assert reg.get("SKL-00000000") is None
        assert reg.get_by_name("nonexistent") is None
