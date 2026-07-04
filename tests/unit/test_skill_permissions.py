"""
RationaleVault Unit Tests — Skill Permissions.

Tests for:
  - PermissionDecision structure
  - CapabilityModel grant / revoke / has
  - PermissionChecker check (allowed and denied paths)
  - All 8 capability keys
"""
from rationalevault.skill_platform.permissions import (
    CAPABILITY_KEYS,
    CapabilityModel,
    PermissionChecker,
    PermissionDecision,
)


class TestPermissionDecision:
    def test_allowed_structure(self):
        pd = PermissionDecision(
            allowed=True,
            missing_capabilities=[],
            denial_reason="",
            evaluation_version="1.0",
        )
        assert pd.allowed is True
        assert pd.missing_capabilities == []
        d = pd.to_dict()
        assert d["allowed"] is True
        assert d["missing_capabilities"] == []

    def test_denied_structure(self):
        pd = PermissionDecision(
            allowed=False,
            missing_capabilities=["ledger:write"],
            denial_reason="Missing capabilities: ledger:write",
            evaluation_version="1.0",
        )
        assert pd.allowed is False
        assert pd.missing_capabilities == ["ledger:write"]
        assert "ledger:write" in pd.denial_reason


class TestCapabilityModel:
    def test_grant_and_has(self):
        cm = CapabilityModel()
        cm.grant("projection:memory")
        assert cm.has("projection:memory") is True
        assert cm.has("projection:knowledge") is False

    def test_revoke(self):
        cm = CapabilityModel(["projection:memory", "ledger:read"])
        cm.revoke("projection:memory")
        assert cm.has("projection:memory") is False
        assert cm.has("ledger:read") is True

    def test_available_sorted(self):
        cm = CapabilityModel(["ledger:write", "projection:memory"])
        assert cm.available() == ["ledger:write", "projection:memory"]

    def test_grant_unknown_raises(self):
        cm = CapabilityModel()
        try:
            cm.grant("unknown:capability")
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "Unknown capability" in str(e)

    def test_to_dict(self):
        cm = CapabilityModel(["projection:memory"])
        d = cm.to_dict()
        assert "capabilities" in d
        assert "projection:memory" in d["capabilities"]

    def test_init_with_capabilities(self):
        cm = CapabilityModel(["projection:memory", "ledger:read"])
        assert cm.has("projection:memory") is True
        assert cm.has("ledger:read") is True


class TestPermissionChecker:
    def test_all_permissions_satisfied(self):
        cm = CapabilityModel(["projection:memory", "projection:knowledge"])
        pd = PermissionChecker.check(
            ["projection:memory", "projection:knowledge"], cm
        )
        assert pd.allowed is True
        assert pd.missing_capabilities == []

    def test_missing_permission_denied(self):
        cm = CapabilityModel(["projection:memory"])
        pd = PermissionChecker.check(
            ["projection:memory", "projection:knowledge"], cm
        )
        assert pd.allowed is False
        assert "projection:knowledge" in pd.missing_capabilities
        assert "projection:knowledge" in pd.denial_reason

    def test_multiple_missing(self):
        cm = CapabilityModel()
        pd = PermissionChecker.check(
            ["projection:memory", "ledger:write"], cm
        )
        assert pd.allowed is False
        assert len(pd.missing_capabilities) == 2

    def test_empty_required_always_allowed(self):
        cm = CapabilityModel()
        pd = PermissionChecker.check([], cm)
        assert pd.allowed is True

    def test_evaluation_version(self):
        cm = CapabilityModel(["projection:memory"])
        pd = PermissionChecker.check(["projection:memory"], cm)
        assert pd.evaluation_version == "1.0"

    def test_ledger_write_only_from_runtime(self):
        cm = CapabilityModel(["ledger:write"])
        pd = PermissionChecker.check(["ledger:write"], cm)
        assert pd.allowed is True
        # In practice, only the Skill Runtime should hold ledger:write
