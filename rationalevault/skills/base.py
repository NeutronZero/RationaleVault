"""
RationaleVault Skills — BaseSkill.

Abstract base class for all skills. Every skill declares its manifest,
capability metadata, and implements __call__(SkillInput) -> SkillOutput.

Design rules:
  - Skills are deterministic: same input → same output.
  - Skills are idempotent by default (override if not).
  - Skills never write to the Event Ledger directly.
  - Skills receive SkillInput, return SkillOutput — no dict→dict.
  - Capability metadata is declarative, not behavioural.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.skill_input import SkillInput
from rationalevault.skill_platform.skill_output import SkillOutput


class BaseSkill(ABC):
    """
    Abstract base class for all skills.

    Subclasses must implement:
      - manifest() -> SkillManifest
      - __call__(skill_input: SkillInput) -> SkillOutput

    Capability metadata is declared as class variables for scheduling
    and policy decisions.
    """

    deterministic: ClassVar[bool] = True
    side_effect_free: ClassVar[bool] = True
    idempotent: ClassVar[bool] = True
    requires_network: ClassVar[bool] = False

    @abstractmethod
    def manifest(self) -> SkillManifest:
        """Return the skill's manifest."""
        ...

    @abstractmethod
    def __call__(self, skill_input: SkillInput) -> SkillOutput:
        """Execute the skill with the given input."""
        ...
