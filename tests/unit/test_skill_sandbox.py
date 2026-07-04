"""
RationaleVault Unit Tests — SkillSandbox.
"""
import time
from rationalevault.skill_platform.sandbox import SkillSandbox, SandboxConfig
from rationalevault.skill_platform.runtime import SandboxViolation


def _fast_skill(inputs: dict) -> dict:
    return {"result": "ok"}


def _slow_skill(inputs: dict) -> dict:
    time.sleep(0.5)
    return {"result": "slow"}


def _failing_skill(inputs: dict) -> dict:
    raise ValueError("skill failed")


class TestSkillSandbox:
    def test_fast_skill_succeeds(self):
        result = SkillSandbox.execute_with_timeout(_fast_skill, {}, 5)
        assert result == {"result": "ok"}

    def test_timeout_raises(self):
        try:
            SkillSandbox.execute_with_timeout(_slow_skill, {}, 0.1)  # 100ms timeout, skill takes 500ms
            assert False, "Should have raised SandboxViolation"
        except SandboxViolation as e:
            assert "timeout" in str(e).lower()

    def test_exception_propagates(self):
        try:
            SkillSandbox.execute_with_timeout(_failing_skill, {}, 5)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "skill failed" in str(e)

    def test_validate_timeout(self):
        assert SkillSandbox.validate_timeout(10, 20) == 10
        assert SkillSandbox.validate_timeout(20, 10) == 10
        assert SkillSandbox.validate_timeout(0, 10) == 10
        assert SkillSandbox.validate_timeout(10, 0) == 10
        assert SkillSandbox.validate_timeout(0, 0) == 0


class TestSandboxConfig:
    def test_to_dict(self):
        c = SandboxConfig(timeout_seconds=30, max_memory_mb=256)
        d = c.to_dict()
        assert d["timeout_seconds"] == 30
        assert d["max_memory_mb"] == 256
