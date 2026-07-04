"""
RationaleVault Skill Platform — SkillSandbox.

Cooperative sandbox using thread-based timeout enforcement.

Design rules:
  - This is a COOPERATIVE sandbox — it cannot stop CPU-bound code.
  - Thread-based timeout works for I/O-bound and sleeping skills.
  - Subprocess isolation is deferred to C3.
  - SandboxViolation is raised on timeout or resource limit.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable

from rationalevault.skill_platform.runtime import SandboxViolation


@dataclass(frozen=True)
class SandboxConfig:
    """Configuration for cooperative sandbox."""
    timeout_seconds: int = 30
    max_memory_mb: int | None = None  # not enforced in C2, reserved for C3

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "max_memory_mb": self.max_memory_mb,
        }


class SkillSandbox:
    """
    Cooperative sandbox using thread-based timeout.

    Wraps skill execution with a thread timer that raises
    SandboxViolation if execution exceeds timeout_seconds.

    Limitations (documented):
      - Cannot stop CPU-bound code (only cooperative timeout)
      - Cannot enforce memory limits (reserved for C3 subprocess)
      - Thread-based timeout works for I/O-bound skills
    """

    @staticmethod
    def execute_with_timeout(
        skill_fn: Callable[[dict[str, Any]], dict[str, Any]],
        inputs: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        """
        Execute a skill function with thread-based timeout.

        Returns the skill's output dict on success.
        Raises SandboxViolation on timeout.
        """
        result: dict[str, Any] = {}
        exception: Exception | None = None
        completed = threading.Event()

        def _target() -> None:
            nonlocal result, exception
            try:
                result = skill_fn(inputs)
            except Exception as exc:
                exception = exc
            finally:
                completed.set()

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()

        if timeout_seconds > 0:
            finished = completed.wait(timeout=timeout_seconds)
            if not finished:
                raise SandboxViolation(
                    f"Skill execution exceeded timeout of {timeout_seconds}s"
                )
        else:
            completed.wait()

        if exception is not None:
            raise exception

        return result

    @staticmethod
    def validate_timeout(timeout_seconds: int, skill_timeout: int) -> int:
        """
        Determine effective timeout.

        Uses the minimum of sandbox config and skill manifest timeout.
        If either is 0, uses the other. If both are 0, no timeout.
        """
        if timeout_seconds <= 0:
            return skill_timeout
        if skill_timeout <= 0:
            return timeout_seconds
        return min(timeout_seconds, skill_timeout)
