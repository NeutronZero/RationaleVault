"""
RationaleVault Skill Platform — Execution Intelligence Models.

Defines Layer 1 to Layer 6 data structures, enums, rules, and builder components
for Epic C5.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =====================================================================
# Layer 1: Execution Analytics
# =====================================================================

@dataclass(frozen=True)
class SkillExecutionStatistics:
    skill_id: str
    total_executions: int
    success_rate: float
    rolling_success_rate: float
    timeouts: int
    schema_failures: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "total_executions": self.total_executions,
            "success_rate": self.success_rate,
            "rolling_success_rate": self.rolling_success_rate,
            "timeouts": self.timeouts,
            "schema_failures": self.schema_failures,
        }


@dataclass(frozen=True)
class PluginExecutionStatistics:
    plugin_id: str
    total_executions: int
    failures: int
    timeouts: int
    denials: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "total_executions": self.total_executions,
            "failures": self.failures,
            "timeouts": self.timeouts,
            "denials": self.denials,
        }


@dataclass(frozen=True)
class ExecutionDurationStatistics:
    skill_id: str
    mean_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "mean_duration_ms": self.mean_duration_ms,
            "min_duration_ms": self.min_duration_ms,
            "max_duration_ms": self.max_duration_ms,
        }


@dataclass(frozen=True)
class ArtifactPromotionStatistics:
    candidate_count: int
    promoted_count: int
    rejected_count: int
    average_gate_score: float
    most_common_violation: str | None
    average_artifact_size: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_count": self.candidate_count,
            "promoted_count": self.promoted_count,
            "rejected_count": self.rejected_count,
            "average_gate_score": self.average_gate_score,
            "most_common_violation": self.most_common_violation,
            "average_artifact_size": self.average_artifact_size,
        }


@dataclass(frozen=True)
class CostBreakdown:
    duration_weight: float
    memory_weight: float
    cpu_weight: float
    total_cost: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_weight": self.duration_weight,
            "memory_weight": self.memory_weight,
            "cpu_weight": self.cpu_weight,
            "total_cost": self.total_cost,
        }


@dataclass(frozen=True)
class ExecutionCostReport:
    duration_ms: int
    cpu_time_ms: int | None
    memory_bytes: int | None
    cost_model_version: str
    cost_components: CostBreakdown

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_ms": self.duration_ms,
            "cpu_time_ms": self.cpu_time_ms,
            "memory_bytes": self.memory_bytes,
            "cost_model_version": self.cost_model_version,
            "cost_components": self.cost_components.to_dict(),
        }


@dataclass(frozen=True)
class ExecutionAnalytics:
    skills: dict[str, SkillExecutionStatistics] = field(default_factory=dict)
    plugins: dict[str, PluginExecutionStatistics] = field(default_factory=dict)
    durations: dict[str, ExecutionDurationStatistics] = field(default_factory=dict)
    promotions: ArtifactPromotionStatistics = field(
        default_factory=lambda: ArtifactPromotionStatistics(0, 0, 0, 0.0, None, 0.0)
    )
    costs: list[ExecutionCostReport] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skills": {k: v.to_dict() for k, v in self.skills.items()},
            "plugins": {k: v.to_dict() for k, v in self.plugins.items()},
            "durations": {k: v.to_dict() for k, v in self.durations.items()},
            "promotions": self.promotions.to_dict(),
            "costs": [c.to_dict() for c in self.costs],
        }

    def compute_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16].upper()


@dataclass(frozen=True)
class ExecutionAnalyticsConfig:
    window_size: int = 5
    trend_epsilon: float = 0.05
    cost_model_version: str = "1.0"
    promotion_weight: float = 1.0


@dataclass(frozen=True)
class ExecutionAnalyticsState:
    version: str
    compiled_at: str
    analytics: ExecutionAnalytics
    analytics_hash: str
    projection_hash: str
    input_snapshot_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "compiled_at": self.compiled_at,
            "analytics": self.analytics.to_dict(),
            "analytics_hash": self.analytics_hash,
            "projection_hash": self.projection_hash,
            "input_snapshot_hash": self.input_snapshot_hash,
        }


# =====================================================================
# Layer 2: Execution Assessment
# =====================================================================

class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    UNHEALTHY = "UNHEALTHY"


class HealthTrend(str, Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"


class AssessmentSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class AssessmentScoreBreakdown:
    reliability_score: float
    performance_score: float
    promotion_score: float
    cost_score: float
    overall_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "reliability_score": self.reliability_score,
            "performance_score": self.performance_score,
            "promotion_score": self.promotion_score,
            "cost_score": self.cost_score,
            "overall_score": self.overall_score,
        }


@dataclass(frozen=True)
class AssessmentRuleResult:
    rule_name: str
    passed: bool
    severity: AssessmentSeverity
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
        }


class AssessmentRule(ABC):
    @abstractmethod
    def evaluate(
        self, analytics: ExecutionAnalytics, config: ExecutionAnalyticsConfig
    ) -> AssessmentRuleResult:
        pass


@dataclass(frozen=True)
class ExecutionAssessment:
    rules: list[AssessmentRuleResult]
    scores: AssessmentScoreBreakdown
    skill_health: dict[str, HealthStatus]
    skill_trends: dict[str, HealthTrend]
    plugin_health: dict[str, HealthStatus]
    assessment_hash: str = ""

    def __post_init__(self) -> None:
        if not self.assessment_hash:
            canonical = json.dumps(
                {
                    "rules": [r.to_dict() for r in self.rules],
                    "scores": self.scores.to_dict(),
                    "skill_health": {k: v.value for k, v in self.skill_health.items()},
                    "skill_trends": {k: v.value for k, v in self.skill_trends.items()},
                    "plugin_health": {k: v.value for k, v in self.plugin_health.items()},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16].upper()
            object.__setattr__(self, "assessment_hash", h)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules": [r.to_dict() for r in self.rules],
            "scores": self.scores.to_dict(),
            "skill_health": {k: v.value for k, v in self.skill_health.items()},
            "skill_trends": {k: v.value for k, v in self.skill_trends.items()},
            "plugin_health": {k: v.value for k, v in self.plugin_health.items()},
            "assessment_hash": self.assessment_hash,
        }


# =====================================================================
# Layer 3: Execution Intelligence
# =====================================================================

class RetryDecision(str, Enum):
    NONE = "NONE"
    IMMEDIATE = "IMMEDIATE"
    BACKOFF = "BACKOFF"
    MANUAL = "MANUAL"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"


@dataclass(frozen=True)
class RetryRecommendation:
    execution_id: str
    result_id: str
    decision: RetryDecision
    reason: str
    recommended_backoff_seconds: int
    max_attempts: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "result_id": self.result_id,
            "decision": self.decision.value,
            "reason": self.reason,
            "recommended_backoff_seconds": self.recommended_backoff_seconds,
            "max_attempts": self.max_attempts,
        }


@dataclass(frozen=True)
class ExecutionFinding:
    severity: AssessmentSeverity
    component: str
    message: str
    related_execution: str | None = None
    related_result: str | None = None
    related_artifact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "component": self.component,
            "message": self.message,
            "related_execution": self.related_execution,
            "related_result": self.related_result,
            "related_artifact": self.related_artifact,
        }


@dataclass(frozen=True)
class ExecutionIntelligence:
    retry_recommendations: list[RetryRecommendation]
    findings: list[ExecutionFinding]
    cost_allocations: dict[str, float]  # skill_id -> total cost allocated

    def to_dict(self) -> dict[str, Any]:
        return {
            "retry_recommendations": [r.to_dict() for r in self.retry_recommendations],
            "findings": [f.to_dict() for f in self.findings],
            "cost_allocations": self.cost_allocations,
        }


# =====================================================================
# Layer 4: Public Report
# =====================================================================

@dataclass(frozen=True)
class ExecutionIntelligenceReport:
    version: str
    created_at: str
    assessment: ExecutionAssessment
    intelligence: ExecutionIntelligence

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "assessment": self.assessment.to_dict(),
            "intelligence": self.intelligence.to_dict(),
        }


# =====================================================================
# Layer 5: Planner Feedback
# =====================================================================

class PlannerRecommendation(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    INCREASE_PRIORITY = "INCREASE_PRIORITY"
    DECREASE_PRIORITY = "DECREASE_PRIORITY"
    DISABLE_PLUGIN = "DISABLE_PLUGIN"
    ENABLE_PLUGIN = "ENABLE_PLUGIN"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    RETRY_PROFILE = "RETRY_PROFILE"


@dataclass(frozen=True)
class PlannerFeedback:
    planner_id: str
    confidence_adjustment: float
    planner_profile_hint: str
    skill_priority_delta: dict[str, float]
    planner_recommendation: PlannerRecommendation
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "planner_id": self.planner_id,
            "confidence_adjustment": self.confidence_adjustment,
            "planner_profile_hint": self.planner_profile_hint,
            "skill_priority_delta": self.skill_priority_delta,
            "planner_recommendation": self.planner_recommendation.value,
            "rationale": self.rationale,
        }


# =====================================================================
# Layer 6: Learning Persistence
# =====================================================================

@dataclass(frozen=True)
class ExecutionLearningRecord:
    learning_id: str
    planner_feedback: PlannerFeedback
    assessment_hash: str
    analytics_hash: str
    evaluation_version: str
    created_at: str
    source_execution_ids: list[str]
    source_artifact_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "learning_id": self.learning_id,
            "planner_feedback": self.planner_feedback.to_dict(),
            "assessment_hash": self.assessment_hash,
            "analytics_hash": self.analytics_hash,
            "evaluation_version": self.evaluation_version,
            "created_at": self.created_at,
            "source_execution_ids": self.source_execution_ids,
            "source_artifact_ids": self.source_artifact_ids,
        }


class LearningRecordBuilder:
    @staticmethod
    def build(
        planner_feedback: PlannerFeedback,
        assessment_hash: str,
        analytics_hash: str,
        evaluation_version: str,
        created_at: str,
        source_execution_ids: list[str],
        source_artifact_ids: list[str],
    ) -> ExecutionLearningRecord:
        # Generate learning_id: LEARN-[hash]
        data = f"learn:{planner_feedback.planner_id}:{evaluation_version}:{assessment_hash}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        learning_id = f"LEARN-{h}"

        return ExecutionLearningRecord(
            learning_id=learning_id,
            planner_feedback=planner_feedback,
            assessment_hash=assessment_hash,
            analytics_hash=analytics_hash,
            evaluation_version=evaluation_version,
            created_at=created_at,
            source_execution_ids=source_execution_ids,
            source_artifact_ids=source_artifact_ids,
        )
