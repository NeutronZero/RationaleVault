"""Governance state structures, dataclasses, and enums."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Set

from rationalevault.recommendation.state import RecommendationCategory


class GovernanceSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class GovernanceAction(Enum):
    NOTIFY = "notify"
    BLOCK = "block"
    SUGGEST = "suggest"
    LOG = "log"


@dataclass(frozen=True)
class GovernanceCondition:
    categories: Optional[Set[RecommendationCategory]] = None
    minimum_priority: Optional[float] = None
    severities: Optional[Set[GovernanceSeverity]] = None


@dataclass(frozen=True)
class GovernanceRuleMetadata:
    id: str
    version: int
    description: str
    severity: GovernanceSeverity
    action: GovernanceAction


@dataclass(frozen=True)
class GovernanceRule:
    metadata: GovernanceRuleMetadata
    condition: GovernanceCondition
    enabled: bool = True


@dataclass(frozen=True)
class RuleEvaluation:
    rule_id: str
    rule_version: int
    matched: bool
    matched_entities: list[str]
    evidence: list[int]          # supporting event sequences
    message: str                 # explanation of match


@dataclass(frozen=True)
class GovernanceWarning:
    id: str                       # deterministic: sha256(projection_version + rule_id + rule_version + entity + sequence)
    rule_id: str
    rule_version: int
    target_entity: str
    severity: GovernanceSeverity
    action: GovernanceAction
    message: str
    evidence: list[int]
    created_at: datetime

    @staticmethod
    def make_id(
        projection_version: int,
        rule_id: str,
        rule_version: int,
        target_entity: str,
        triggering_sequence: int,
    ) -> str:
        """Generate a deterministic governance warning ID."""
        raw = (
            f"{projection_version}:{rule_id}:"
            f"{rule_version}:{target_entity}:"
            f"{triggering_sequence}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class GovernanceState:
    rules: list[GovernanceRule] = field(default_factory=list)
    sequence: int = 0

    @property
    def rule_count(self) -> int:
        return len(self.rules)
