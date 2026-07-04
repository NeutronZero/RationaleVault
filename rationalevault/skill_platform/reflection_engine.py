from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from rationalevault.skill_platform.intelligence_models import (
    ExecutionLearningRecord,
    PlannerRecommendation,
)
from rationalevault.skill_platform.reflection_models import (
    ReflectionReason,
    ReflectionStatus,
    ReflectionConfig,
    ReflectionCandidate,
    Reflection,
)
from rationalevault.skill_platform.reflection_events import (
    ReflectionCandidateCreatedPayload,
    ReflectionAssessedPayload,
    ReflectionGeneratedPayload,
    ReflectionTracedPayload,
    RuleResultPayload,
    RuleTracePayload,
    generate_assessment_id,
    generate_reflection_trace_id,
    SCHEMA_VERSION,
)


@dataclass(frozen=True)
class ReflectionAssessment:
    """The outcome of evaluating rules on a ReflectionCandidate.

    This is an EPHEMERAL implementation detail. The persisted contract is
    ReflectionAssessedPayload (emitted as REFLECTION_ASSESSED event).
    """
    candidate_id: str
    approved: bool
    confidence: float
    base_confidence: float
    recurrence_score: float
    contradiction_penalty: float
    duplicate_suppressed: bool
    reasons_for_decision: list[str]
    supporting_record_ids: list[str]
    passed_rules: list[str]
    failed_rules: list[str]
    triggered_rules: list[str]
    rule_scores: dict[str, float]

    def to_payload(self, created_at: str) -> ReflectionAssessedPayload:
        """Convert ephemeral assessment to persisted event payload."""
        rules_evaluated = []
        for rule_name in self.triggered_rules:
            passed = rule_name in self.passed_rules
            # Find the reason from reasons_for_decision
            reason = ""
            for r in self.reasons_for_decision:
                if r.startswith(rule_name + ":"):
                    reason = r.split(": ", 1)[1] if ": " in r else ""
                    break
            rules_evaluated.append(RuleResultPayload(
                rule_name=rule_name,
                passed=passed,
                reason=reason,
            ))

        return ReflectionAssessedPayload(
            schema_version=SCHEMA_VERSION,
            assessment_id=generate_assessment_id(self.candidate_id, created_at),
            candidate_id=self.candidate_id,
            approved=self.approved,
            confidence=self.confidence,
            base_confidence=self.base_confidence,
            recurrence_score=self.recurrence_score,
            contradiction_penalty=self.contradiction_penalty,
            duplicate_suppressed=self.duplicate_suppressed,
            rules_evaluated=rules_evaluated,
            supporting_record_ids=self.supporting_record_ids,
            created_at=created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "approved": self.approved,
            "confidence": round(self.confidence, 4),
            "base_confidence": round(self.base_confidence, 4),
            "recurrence_score": round(self.recurrence_score, 4),
            "contradiction_penalty": round(self.contradiction_penalty, 4),
            "duplicate_suppressed": self.duplicate_suppressed,
            "reasons_for_decision": self.reasons_for_decision,
            "supporting_record_ids": self.supporting_record_ids,
            "passed_rules": self.passed_rules,
            "failed_rules": self.failed_rules,
            "triggered_rules": self.triggered_rules,
            "rule_scores": self.rule_scores,
        }


class ReflectionCandidateBuilder:
    """Consumes ExecutionLearningRecord instances and groups them to produce ReflectionCandidates.

    Domain objects (ReflectionCandidate) are implementation details.
    Event payloads (ReflectionCandidateCreatedPayload) are the persisted contracts.
    """

    @staticmethod
    def build_candidates(
        records: list[ExecutionLearningRecord],
        config: ReflectionConfig,
        created_at: str | None = None
    ) -> list[ReflectionCandidate]:
        if not config.enabled:
            return []

        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()

        # Group learning records by target (skill_id or planner_id)
        by_target: dict[str, list[ExecutionLearningRecord]] = {}
        for record in records:
            targets = list(record.planner_feedback.skill_priority_delta.keys())
            if not targets:
                targets = [record.planner_feedback.planner_id]

            for target in targets:
                by_target.setdefault(target, []).append(record)

        candidates: list[ReflectionCandidate] = []

        for target, target_records in by_target.items():
            supporting: list[ExecutionLearningRecord] = []
            conflicting: list[ExecutionLearningRecord] = []
            timeouts_count = 0
            failures_count = 0
            planner_errors_count = 0

            for rec in target_records:
                fb = rec.planner_feedback
                rationale_lower = fb.rationale.lower()

                is_timeout = "timeout" in rationale_lower or "performance" in rationale_lower
                is_failure = (
                    fb.confidence_adjustment < 0
                    or fb.planner_recommendation in (
                        PlannerRecommendation.DECREASE_PRIORITY,
                        PlannerRecommendation.DISABLE_PLUGIN,
                        PlannerRecommendation.MANUAL_REVIEW
                    )
                )

                if is_timeout:
                    timeouts_count += 1
                    supporting.append(rec)
                elif is_failure:
                    failures_count += 1
                    supporting.append(rec)
                    if fb.planner_recommendation == PlannerRecommendation.MANUAL_REVIEW:
                        planner_errors_count += 1
                else:
                    conflicting.append(rec)

            if not supporting:
                continue

            if timeouts_count >= 2:
                reason = ReflectionReason.PERFORMANCE_DEGRADATION
            elif planner_errors_count > 0:
                reason = ReflectionReason.LOW_CONFIDENCE
            else:
                reason = ReflectionReason.OUTCOME_MISMATCH

            if reason not in config.enabled_reasons:
                continue

            latest_record = max(supporting, key=lambda r: r.created_at)
            source_artifact_id = latest_record.source_artifact_ids[0] if latest_record.source_artifact_ids else "UNKNOWN-ART"

            context = {
                "target": target,
                "supporting_record_ids": [r.learning_id for r in supporting],
                "conflicting_record_ids": [r.learning_id for r in conflicting],
                "recurrence_count": len(supporting),
                "timeouts_count": timeouts_count,
                "failures_count": failures_count,
                "rationales": [r.planner_feedback.rationale for r in supporting],
                "recommendations": [r.planner_feedback.planner_recommendation.value for r in supporting],
            }

            candidate_id = ReflectionCandidate.generate_candidate_id(
                source_artifact_id=source_artifact_id,
                reason=reason,
                config_version=config.version
            )

            candidates.append(
                ReflectionCandidate(
                    candidate_id=candidate_id,
                    source_artifact_id=source_artifact_id,
                    reason=reason,
                    context=context,
                    created_at=created_at,
                    config_version=config.version,
                )
            )

        return candidates

    @staticmethod
    def build_payloads(
        candidates: list[ReflectionCandidate],
        created_at: str
    ) -> list[ReflectionCandidateCreatedPayload]:
        """Convert domain candidates to event payloads for ledger emission."""
        payloads = []
        for c in candidates:
            payloads.append(ReflectionCandidateCreatedPayload(
                schema_version=SCHEMA_VERSION,
                candidate_id=c.candidate_id,
                source_artifact_id=c.source_artifact_id,
                reason=c.reason.value,
                context=c.context,
                created_at=created_at,
                config_version=c.config_version,
            ))
        return payloads


class ReflectionRule(ABC):
    """Abstract base class for deterministic evaluation rules."""
    @abstractmethod
    def evaluate(self, candidate: ReflectionCandidate, config: ReflectionConfig) -> tuple[bool, str]:
        """Evaluates the candidate against a specific rule. Returns (passed, message)."""
        pass


class MinSupportingRecordsRule(ReflectionRule):
    def __init__(self, min_records: int = 2):
        self.min_records = min_records

    def evaluate(self, candidate: ReflectionCandidate, config: ReflectionConfig) -> tuple[bool, str]:
        supporting_ids = candidate.context.get("supporting_record_ids", [])
        if len(supporting_ids) < self.min_records:
            return False, f"Insufficient supporting records: got {len(supporting_ids)}, need {self.min_records}"
        return True, f"Met minimum supporting records threshold ({len(supporting_ids)} >= {self.min_records})"


class RecurrenceThresholdRule(ReflectionRule):
    def __init__(self, threshold: int = 2):
        self.threshold = threshold

    def evaluate(self, candidate: ReflectionCandidate, config: ReflectionConfig) -> tuple[bool, str]:
        recurrence = candidate.context.get("recurrence_count", 1)
        if recurrence < self.threshold:
            return False, f"Issue did not recur enough: count {recurrence} < threshold {self.threshold}"
        return True, f"Recurrence threshold met ({recurrence} >= {self.threshold})"


class ConflictingEvidenceRule(ReflectionRule):
    def evaluate(self, candidate: ReflectionCandidate, config: ReflectionConfig) -> tuple[bool, str]:
        conflicts = candidate.context.get("conflicting_record_ids", [])
        supporting = candidate.context.get("supporting_record_ids", [])
        if len(conflicts) > 0 and len(conflicts) >= len(supporting):
            return False, f"Conflicting evidence matches or exceeds supporting evidence: {len(conflicts)} vs {len(supporting)}"
        return True, f"Conflicting evidence check passed (conflicts: {len(conflicts)}, supporting: {len(supporting)})"


class MinConfidenceRule(ReflectionRule):
    def evaluate(self, candidate: ReflectionCandidate, config: ReflectionConfig) -> tuple[bool, str]:
        base_conf = 0.5
        recurrence_bonus = min(0.4, (candidate.context.get("recurrence_count", 1) - 1) * 0.1)
        conflict_penalty = len(candidate.context.get("conflicting_record_ids", [])) * 0.15
        confidence = max(0.0, min(1.0, base_conf + recurrence_bonus - conflict_penalty))

        if confidence < config.confidence_threshold:
            return False, f"Confidence score {confidence:.2f} is below config threshold {config.confidence_threshold:.2f}"
        return True, f"Confidence score {confidence:.2f} satisfies config threshold {config.confidence_threshold:.2f}"


class DuplicateSuppressionRule(ReflectionRule):
    def __init__(self, active_targets: set[str]):
        self.active_targets = active_targets

    def evaluate(self, candidate: ReflectionCandidate, config: ReflectionConfig) -> tuple[bool, str]:
        target = candidate.context.get("target")
        if target in self.active_targets:
            return False, f"Duplicate reflection suppression: target '{target}' has an active reflection"
        return True, "No duplicate active reflection detected for target"


class ReflectionRuleEngine:
    """Evaluates rules on candidates to produce assessments."""
    def __init__(self, rules: list[ReflectionRule]):
        self.rules = rules

    def assess(self, candidate: ReflectionCandidate, config: ReflectionConfig) -> ReflectionAssessment:
        reasons_for_decision: list[str] = []
        approved = True
        duplicate_suppressed = False
        passed_rules: list[str] = []
        failed_rules: list[str] = []
        triggered_rules: list[str] = []
        rule_scores: dict[str, float] = {}

        base_confidence = 0.5
        recurrence_bonus = min(0.4, (candidate.context.get("recurrence_count", 1) - 1) * 0.1)
        conflict_penalty = len(candidate.context.get("conflicting_record_ids", [])) * 0.15
        confidence = max(0.0, min(1.0, base_confidence + recurrence_bonus - conflict_penalty))

        for rule in self.rules:
            rule_name = rule.__class__.__name__
            triggered_rules.append(rule_name)
            passed, msg = rule.evaluate(candidate, config)
            reasons_for_decision.append(f"{rule_name}: {'PASSED' if passed else 'FAILED'} - {msg}")
            
            # Score assignment
            if isinstance(rule, MinConfidenceRule):
                rule_scores[rule_name] = confidence
            else:
                rule_scores[rule_name] = 1.0 if passed else 0.0

            if passed:
                passed_rules.append(rule_name)
            else:
                failed_rules.append(rule_name)
                approved = False
                if isinstance(rule, DuplicateSuppressionRule):
                    duplicate_suppressed = True

        return ReflectionAssessment(
            candidate_id=candidate.candidate_id,
            approved=approved,
            confidence=confidence,
            base_confidence=base_confidence,
            recurrence_score=recurrence_bonus,
            contradiction_penalty=conflict_penalty,
            duplicate_suppressed=duplicate_suppressed,
            reasons_for_decision=reasons_for_decision,
            supporting_record_ids=candidate.context.get("supporting_record_ids", []),
            passed_rules=passed_rules,
            failed_rules=failed_rules,
            triggered_rules=triggered_rules,
            rule_scores=rule_scores,
        )


class ReflectionCompiler:
    """Compiles approved assessments into first-class Reflection objects.

    Domain objects (Reflection) are implementation details.
    Event payloads (ReflectionGeneratedPayload, ReflectionTracedPayload) are the persisted contracts.
    """

    @staticmethod
    def compile(
        assessment: ReflectionAssessment,
        candidate: ReflectionCandidate,
        created_at: str | None = None
    ) -> Reflection:
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()

        target = candidate.context.get("target", "UNKNOWN")
        rationales = candidate.context.get("rationales", [])
        recommendations = candidate.context.get("recommendations", [])

        insights = [
            f"Target {target} triggered {candidate.reason.value} due to recurrent issues.",
        ]
        for rat in rationales:
            if rat and rat not in insights:
                insights.append(f"Observer feedback: {rat}")

        reconstructed_rationale = (
            f"Reflection triggered for target '{target}' via candidate {candidate.candidate_id}. "
            f"Supporting records: {len(assessment.supporting_record_ids)}. "
            f"Calculated confidence: {assessment.confidence:.2f}."
        )

        actionable_guidelines = []
        for rec in set(recommendations):
            actionable_guidelines.append(f"Planner Action Recommended: {rec} for target {target}")
        if candidate.reason == ReflectionReason.PERFORMANCE_DEGRADATION:
            actionable_guidelines.append(f"Performance Warning: Adjust execution timeouts and retry profile for {target}")
        elif candidate.reason == ReflectionReason.LOW_CONFIDENCE:
            actionable_guidelines.append(f"Confidence Warning: Require manual verification before promoting output from {target}")

        reflection_id = Reflection.generate_reflection_id(candidate.candidate_id, created_at)

        return Reflection(
            reflection_id=reflection_id,
            candidate_id=candidate.candidate_id,
            status=ReflectionStatus.COMPLETED if assessment.approved else ReflectionStatus.REJECTED,
            insights=insights,
            reconstructed_rationale=reconstructed_rationale,
            actionable_guidelines=actionable_guidelines,
            created_at=created_at,
            completed_at=created_at if assessment.approved else None,
        )

    @staticmethod
    def compile_generated_payload(
        reflection: Reflection,
        source_learning_record_ids: list[str],
        created_at: str
    ) -> ReflectionGeneratedPayload:
        """Convert domain Reflection to event payload for ledger emission."""
        return ReflectionGeneratedPayload(
            schema_version=SCHEMA_VERSION,
            reflection_id=reflection.reflection_id,
            candidate_id=reflection.candidate_id,
            status=reflection.status.value,
            insights=reflection.insights,
            reconstructed_rationale=reflection.reconstructed_rationale,
            actionable_guidelines=reflection.actionable_guidelines,
            source_learning_record_ids=source_learning_record_ids,
            created_at=created_at,
        )

    @staticmethod
    def compile_traced_payload(
        assessment: ReflectionAssessment,
        reflection_id: str,
        candidate: ReflectionCandidate,
        created_at: str
    ) -> ReflectionTracedPayload:
        """Compile assessment into a trace payload for audit trail."""
        rules_fired = []
        for rule_name in assessment.triggered_rules:
            passed = rule_name in assessment.passed_rules
            reason = ""
            inputs: dict[str, Any] = {}
            for r in assessment.reasons_for_decision:
                if r.startswith(rule_name + ":"):
                    reason = r.split(": ", 1)[1] if ": " in r else ""
                    break
            # Extract inputs from candidate context for relevant rules
            if rule_name == "MinSupportingRecordsRule":
                inputs = {"supporting_count": len(assessment.supporting_record_ids)}
            elif rule_name == "MinConfidenceRule":
                inputs = {"confidence": assessment.confidence}
            rules_fired.append(RuleTracePayload(
                rule_name=rule_name,
                passed=passed,
                reason=reason,
                inputs=inputs,
            ))

        all_record_ids = candidate.context.get("supporting_record_ids", []) + candidate.context.get("conflicting_record_ids", [])
        contributing = [rid for rid in all_record_ids if rid in assessment.supporting_record_ids]
        ignored = [rid for rid in all_record_ids if rid not in assessment.supporting_record_ids]

        trace_id = generate_reflection_trace_id(reflection_id, candidate.candidate_id, created_at)

        return ReflectionTracedPayload(
            schema_version=SCHEMA_VERSION,
            trace_id=trace_id,
            reflection_id=reflection_id,
            candidate_id=candidate.candidate_id,
            approved=assessment.approved,
            confidence=assessment.confidence,
            rules_fired=rules_fired,
            contributing_learning_records=contributing,
            ignored_learning_records=ignored,
            duplicate_suppressed=assessment.duplicate_suppressed,
            conflict_resolution=None,
            created_at=created_at,
        )
