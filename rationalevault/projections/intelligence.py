"""
RationaleVault Skill Platform — Execution Intelligence Projection.

Computes Layer 2 (Assessment), Layer 3 (Intelligence), Layer 4 (Report),
and Layer 5 (Feedback) from analytics and execution state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar

from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.schema.events import EventRecord
from rationalevault.skill_platform.execution_state import ExecutionStateProjection
from rationalevault.projections.analytics import ExecutionAnalyticsProjection
from rationalevault.skill_platform.intelligence_models import (
    ExecutionAnalytics,
    ExecutionAnalyticsConfig,
    ExecutionAssessment,
    AssessmentScoreBreakdown,
    AssessmentRuleResult,
    AssessmentRule,
    AssessmentSeverity,
    HealthStatus,
    HealthTrend,
    RetryDecision,
    RetryRecommendation,
    ExecutionFinding,
    ExecutionIntelligence,
    ExecutionIntelligenceReport,
)


class ReliabilityRule(AssessmentRule):
    def evaluate(
        self, analytics: ExecutionAnalytics, config: ExecutionAnalyticsConfig
    ) -> AssessmentRuleResult:
        failures = []
        for skill_id, stats in analytics.skills.items():
            if stats.success_rate < 0.90:
                failures.append(f"Skill '{skill_id}' success rate {stats.success_rate:.2f} is below 0.90")
        if failures:
            return AssessmentRuleResult(
                rule_name="ReliabilityRule",
                passed=False,
                severity=AssessmentSeverity.WARNING,
                message="; ".join(failures),
            )
        return AssessmentRuleResult(
            rule_name="ReliabilityRule",
            passed=True,
            severity=AssessmentSeverity.INFO,
            message="All skills have success rate >= 0.90",
        )


class TimeoutRule(AssessmentRule):
    def evaluate(
        self, analytics: ExecutionAnalytics, config: ExecutionAnalyticsConfig
    ) -> AssessmentRuleResult:
        total_timeouts = sum(s.timeouts for s in analytics.skills.values())
        if total_timeouts > 0:
            return AssessmentRuleResult(
                rule_name="TimeoutRule",
                passed=False,
                severity=AssessmentSeverity.WARNING,
                message=f"Detected {total_timeouts} execution timeouts in historical records",
            )
        return AssessmentRuleResult(
            rule_name="TimeoutRule",
            passed=True,
            severity=AssessmentSeverity.INFO,
            message="No timeouts recorded",
        )


class ExecutionIntelligenceProjection(BaseProjection):
    """
    ExecutionIntelligenceProjection evaluates assessment rules and produces intelligence reports.
    """
    projection_name: ClassVar[str] = "execution_intelligence"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
    dependencies: ClassVar[list[type[BaseProjection]]] = [ExecutionAnalyticsProjection]
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 98

    @staticmethod
    def project(
        events: list[EventRecord],
        config: ExecutionAnalyticsConfig = ExecutionAnalyticsConfig(),
        known_decision_ids: list[str] | None = None,
    ) -> ExecutionIntelligenceReport:
        # 1. Compile analytics
        analytics_state = ExecutionAnalyticsProjection.project(events, config, known_decision_ids)
        analytics = analytics_state.analytics

        # 2. Evaluate rules
        rules = [
            ReliabilityRule().evaluate(analytics, config),
            TimeoutRule().evaluate(analytics, config),
        ]

        # 3. Calculate scores
        # Basic scoring formulas
        overall_rules_passed = sum(1 for r in rules if r.passed)
        reliability_score = (
            sum(s.success_rate for s in analytics.skills.values()) / len(analytics.skills)
            if analytics.skills
            else 1.0
        )
        performance_score = 1.0  # Default perfect performance unless degraded
        promotion_score = (
            analytics.promotions.promoted_count / analytics.promotions.candidate_count
            if analytics.promotions.candidate_count > 0
            else 1.0
        )
        cost_score = 1.0
        
        overall_score = (
            reliability_score * 0.4
            + performance_score * 0.2
            + promotion_score * 0.2
            + cost_score * 0.2
        ) * (overall_rules_passed / len(rules) if rules else 1.0)

        scores = AssessmentScoreBreakdown(
            reliability_score=round(reliability_score, 4),
            performance_score=round(performance_score, 4),
            promotion_score=round(promotion_score, 4),
            cost_score=round(cost_score, 4),
            overall_score=round(overall_score, 4),
        )

        # 4. Skill Health & Trend classifications
        skill_health = {}
        skill_trends = {}
        for skill_id, stats in analytics.skills.items():
            # Trend calculation
            if stats.rolling_success_rate > stats.success_rate + config.trend_epsilon:
                skill_trends[skill_id] = HealthTrend.IMPROVING
            elif stats.rolling_success_rate < stats.success_rate - config.trend_epsilon:
                skill_trends[skill_id] = HealthTrend.DEGRADING
            else:
                skill_trends[skill_id] = HealthTrend.STABLE

            # Health classification
            if stats.rolling_success_rate < 0.8:
                skill_health[skill_id] = HealthStatus.UNHEALTHY
            elif stats.rolling_success_rate < 0.95 or stats.timeouts > 0:
                skill_health[skill_id] = HealthStatus.WARNING
            else:
                skill_health[skill_id] = HealthStatus.HEALTHY

        # Plugin health
        plugin_health = {}
        for plugin_id, stats in analytics.plugins.items():
            if stats.total_executions > 0:
                err_rate = (stats.failures + stats.timeouts) / stats.total_executions
                if err_rate >= 0.20:
                    plugin_health[plugin_id] = HealthStatus.UNHEALTHY
                elif err_rate > 0.0:
                    plugin_health[plugin_id] = HealthStatus.WARNING
                else:
                    plugin_health[plugin_id] = HealthStatus.HEALTHY
            else:
                plugin_health[plugin_id] = HealthStatus.HEALTHY

        assessment = ExecutionAssessment(
            rules=rules,
            scores=scores,
            skill_health=skill_health,
            skill_trends=skill_trends,
            plugin_health=plugin_health,
        )

        # 5. Interpretations & Retry recommendations
        # Retrieve base ExecutionState to inspect failures directly
        state = ExecutionStateProjection.build(events, known_decision_ids)
        retry_recs = []
        findings = []
        cost_allocations = {}

        # Scan for failed runs
        for e in state.failed_executions + state.timeout_executions + state.denied_executions:
            # If timeout -> BACKOFF
            if e.state == "TIMEOUT":
                rec = RetryRecommendation(
                    execution_id=e.execution_id,
                    result_id=e.output_hash or "UNKNOWN",
                    decision=RetryDecision.BACKOFF,
                    reason="Transient execution timeout detected",
                    recommended_backoff_seconds=10,
                    max_attempts=3,
                )
                retry_recs.append(rec)
                findings.append(
                    ExecutionFinding(
                        severity=AssessmentSeverity.WARNING,
                        component="SkillRuntime",
                        message=f"Timeout violation in execution {e.execution_id}",
                        related_execution=e.execution_id,
                    )
                )
            # If denied or schema failure -> PERMANENT_FAILURE
            elif e.error and ("validation failed" in e.error.lower() or "missing capabilities" in e.error.lower()):
                rec = RetryRecommendation(
                    execution_id=e.execution_id,
                    result_id=e.output_hash or "UNKNOWN",
                    decision=RetryDecision.PERMANENT_FAILURE,
                    reason=f"Non-transient execution error: {e.error}",
                    recommended_backoff_seconds=0,
                    max_attempts=1,
                )
                retry_recs.append(rec)
                findings.append(
                    ExecutionFinding(
                        severity=AssessmentSeverity.CRITICAL,
                        component="Executor",
                        message=f"Permanent failure: {e.error}",
                        related_execution=e.execution_id,
                    )
                )
            else:
                # Default failure -> IMMEDIATE retry
                rec = RetryRecommendation(
                    execution_id=e.execution_id,
                    result_id=e.output_hash or "UNKNOWN",
                    decision=RetryDecision.IMMEDIATE,
                    reason="Execution failed; immediate retry recommended",
                    recommended_backoff_seconds=0,
                    max_attempts=3,
                )
                retry_recs.append(rec)

        # Cost allocation calculation
        for cost_rep in analytics.costs:
            # Map cost report to skill using durations stats or default
            pass
        # Simple default mapping
        for skill_id, stats in analytics.skills.items():
            dur_stats = analytics.durations.get(skill_id)
            if dur_stats:
                cost_allocations[skill_id] = dur_stats.mean_duration_ms * stats.total_executions * 0.0001
            else:
                cost_allocations[skill_id] = 0.0

        intelligence = ExecutionIntelligence(
            retry_recommendations=retry_recs,
            findings=findings,
            cost_allocations=cost_allocations,
        )

        created_at = datetime.now(timezone.utc).isoformat()

        return ExecutionIntelligenceReport(
            version="1.0.0",
            created_at=created_at,
            assessment=assessment,
            intelligence=intelligence,
        )
