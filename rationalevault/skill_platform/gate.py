"""
RationaleVault Skill Platform — Execution Gates.

Implements the execution evaluation assessment, extensible gate rules, policy enforcement,
and promotion logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rationalevault.skill_platform.artifact import Artifact, ArtifactCandidate


class PromotionDecisionType(str, Enum):
    """Possible outcomes of an execution promotion decision."""
    PASS = "PASS"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class ExecutionScoreBreakdown:
    """Detailed components contributing to the overall execution score."""
    success_component: float
    timeout_penalty: float
    denial_penalty: float
    validation_penalty: float
    policy_bonus: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "success_component": self.success_component,
            "timeout_penalty": self.timeout_penalty,
            "denial_penalty": self.denial_penalty,
            "validation_penalty": self.validation_penalty,
            "policy_bonus": self.policy_bonus,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExecutionScoreBreakdown:
        return cls(
            success_component=d["success_component"],
            timeout_penalty=d["timeout_penalty"],
            denial_penalty=d["denial_penalty"],
            validation_penalty=d["validation_penalty"],
            policy_bonus=d["policy_bonus"],
        )


@dataclass(frozen=True)
class ExecutionEvaluation:
    """
    Deterministic measurement of execution quality.
    
    Answers the question: what happened?
    """
    version: str = "1.0"
    success_rate: float = 0.0
    timeout_rate: float = 0.0
    denial_rate: float = 0.0
    passed: bool = False
    score: float = 0.0
    breakdown: ExecutionScoreBreakdown = field(
        default_factory=lambda: ExecutionScoreBreakdown(0.0, 0.0, 0.0, 0.0, 0.0)
    )
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "success_rate": self.success_rate,
            "timeout_rate": self.timeout_rate,
            "denial_rate": self.denial_rate,
            "passed": self.passed,
            "score": self.score,
            "breakdown": self.breakdown.to_dict(),
            "findings": self.findings,
            "warnings": self.warnings,
            "recommended_actions": self.recommended_actions,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExecutionEvaluation:
        return cls(
            version=d.get("version", "1.0"),
            success_rate=d.get("success_rate", 0.0),
            timeout_rate=d.get("timeout_rate", 0.0),
            denial_rate=d.get("denial_rate", 0.0),
            passed=d.get("passed", False),
            score=d.get("score", 0.0),
            breakdown=ExecutionScoreBreakdown.from_dict(d["breakdown"]) if "breakdown" in d else ExecutionScoreBreakdown(0.0, 0.0, 0.0, 0.0, 0.0),
            findings=d.get("findings", []),
            warnings=d.get("warnings", []),
            recommended_actions=d.get("recommended_actions", []),
        )


@dataclass(frozen=True)
class ExecutionGatePolicy:
    """Configurable threshold rules for execution gates."""
    version: str = "1.0"
    min_success_rate: float = 0.90
    max_timeout_rate: float = 0.05
    max_denial_rate: float = 0.05
    min_overall_score: float = 0.95
    allow_warnings: bool = True
    max_warnings: int = 5
    require_provenance: bool = True
    max_duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "min_success_rate": self.min_success_rate,
            "max_timeout_rate": self.max_timeout_rate,
            "max_denial_rate": self.max_denial_rate,
            "min_overall_score": self.min_overall_score,
            "allow_warnings": self.allow_warnings,
            "max_warnings": self.max_warnings,
            "require_provenance": self.require_provenance,
            "max_duration_ms": self.max_duration_ms,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExecutionGatePolicy:
        return cls(
            version=d.get("version", "1.0"),
            min_success_rate=d.get("min_success_rate", 0.90),
            max_timeout_rate=d.get("max_timeout_rate", 0.05),
            max_denial_rate=d.get("max_denial_rate", 0.05),
            min_overall_score=d.get("min_overall_score", 0.95),
            allow_warnings=d.get("allow_warnings", True),
            max_warnings=d.get("max_warnings", 5),
            require_provenance=d.get("require_provenance", True),
            max_duration_ms=d.get("max_duration_ms"),
        )


@dataclass(frozen=True)
class GateResult:
    """Structured result of applying an execution gate to an evaluation."""
    decision: PromotionDecisionType
    violations: list[str]
    warnings: list[str]
    evaluated_policy_version: str
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "decision": self.decision.value,
            "violations": self.violations,
            "warnings": self.warnings,
            "evaluated_policy_version": self.evaluated_policy_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GateResult:
        return cls(
            decision=PromotionDecisionType(d["decision"]),
            violations=d.get("violations", []),
            warnings=d.get("warnings", []),
            evaluated_policy_version=d["evaluated_policy_version"],
            version=d.get("version", "1.0"),
        )


@dataclass(frozen=True)
class PromotionDecision:
    """
    Immutable promotion decision record.
    
    Answers: exactly what should be promoted?
    """
    decision: PromotionDecisionType
    artifact_ids: list[str]
    reasons: list[str]
    policy_version: str
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "decision": self.decision.value,
            "artifact_ids": self.artifact_ids,
            "reasons": self.reasons,
            "policy_version": self.policy_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PromotionDecision:
        return cls(
            decision=PromotionDecisionType(d["decision"]),
            artifact_ids=d.get("artifact_ids", []),
            reasons=d.get("reasons", []),
            policy_version=d["policy_version"],
            version=d.get("version", "1.0"),
        )


@dataclass(frozen=True)
class ArtifactPromotionReport:
    """
    Immutable report of the artifact promotion process.

    Contains details of promoted artifacts, rejected candidates, and policy decisions.
    """
    promoted: list[Artifact]
    rejected: list[ArtifactCandidate]
    decision: PromotionDecision
    gate_result: GateResult
    evaluation: ExecutionEvaluation
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "promoted": [a.to_dict() for a in self.promoted],
            "rejected": [r.to_dict() for r in self.rejected],
            "decision": self.decision.to_dict(),
            "gate_result": self.gate_result.to_dict(),
            "evaluation": self.evaluation.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ArtifactPromotionReport:
        return cls(
            promoted=[Artifact.from_dict(a) for a in d.get("promoted", [])],
            rejected=[ArtifactCandidate.from_dict(r) for r in d.get("rejected", [])],
            decision=PromotionDecision.from_dict(d["decision"]),
            gate_result=GateResult.from_dict(d["gate_result"]),
            evaluation=ExecutionEvaluation.from_dict(d["evaluation"]),
            version=d.get("version", "1.0"),
        )



class GateRule(ABC):
    """Abstract base class for extensible execution gate rules."""

    @abstractmethod
    def evaluate(
        self, evaluation: ExecutionEvaluation, policy: ExecutionGatePolicy
    ) -> tuple[bool, str | None]:
        """
        Evaluate rule against execution evaluation and policy.

        Returns (passed, violation_reason).
        """
        pass


class SuccessRateRule(GateRule):
    """Asserts that the success rate meets the minimum requirement."""

    def evaluate(
        self, evaluation: ExecutionEvaluation, policy: ExecutionGatePolicy
    ) -> tuple[bool, str | None]:
        if evaluation.success_rate < policy.min_success_rate:
            return (
                False,
                f"Success rate {evaluation.success_rate:.2f} below minimum {policy.min_success_rate:.2f}",
            )
        return True, None


class TimeoutRateRule(GateRule):
    """Asserts that the timeout rate does not exceed the maximum limit."""

    def evaluate(
        self, evaluation: ExecutionEvaluation, policy: ExecutionGatePolicy
    ) -> tuple[bool, str | None]:
        if evaluation.timeout_rate > policy.max_timeout_rate:
            return (
                False,
                f"Timeout rate {evaluation.timeout_rate:.2f} exceeds maximum {policy.max_timeout_rate:.2f}",
            )
        return True, None


class DenialRateRule(GateRule):
    """Asserts that the denial rate does not exceed the maximum limit."""

    def evaluate(
        self, evaluation: ExecutionEvaluation, policy: ExecutionGatePolicy
    ) -> tuple[bool, str | None]:
        if evaluation.denial_rate > policy.max_denial_rate:
            return (
                False,
                f"Denial rate {evaluation.denial_rate:.2f} exceeds maximum {policy.max_denial_rate:.2f}",
            )
        return True, None


class OverallScoreRule(GateRule):
    """Asserts that the overall evaluation score is acceptable."""

    def evaluate(
        self, evaluation: ExecutionEvaluation, policy: ExecutionGatePolicy
    ) -> tuple[bool, str | None]:
        if evaluation.score < policy.min_overall_score:
            return (
                False,
                f"Overall score {evaluation.score:.2f} below minimum {policy.min_overall_score:.2f}",
            )
        return True, None


class ExecutionGate:
    """
    Applies gate rules to an execution evaluation to check policy compliance.
    
    Answers the question: is this acceptable?
    """

    @staticmethod
    def evaluate(
        evaluation: ExecutionEvaluation,
        policy: ExecutionGatePolicy,
        rules: list[GateRule] | None = None,
    ) -> GateResult:
        if rules is None:
            rules = [
                SuccessRateRule(),
                TimeoutRateRule(),
                DenialRateRule(),
                OverallScoreRule(),
            ]

        violations: list[str] = []
        warnings: list[str] = []

        # Validate warning rules
        if not policy.allow_warnings and len(evaluation.warnings) > 0:
            violations.append("Policy forbids execution warnings")
        elif len(evaluation.warnings) > policy.max_warnings:
            violations.append(
                f"Warnings count {len(evaluation.warnings)} exceeds max {policy.max_warnings}"
            )

        # Run custom rules
        for rule in rules:
            passed, reason = rule.evaluate(evaluation, policy)
            if not passed and reason:
                violations.append(reason)

        warnings.extend(evaluation.warnings)

        # Determine decision
        if violations:
            decision = PromotionDecisionType.BLOCK
        elif warnings:
            decision = PromotionDecisionType.REVIEW
        else:
            decision = PromotionDecisionType.PASS

        return GateResult(
            decision=decision,
            violations=violations,
            warnings=warnings,
            evaluated_policy_version=policy.version,
        )


class ExecutionPromoter:
    """Evaluates promotion choices for ArtifactCandidates based on GateResults."""

    @staticmethod
    def promote(
        gate_result: GateResult,
        candidates: list[ArtifactCandidate],
        policy_version: str,
    ) -> PromotionDecision:
        reasons: list[str] = []
        artifact_ids: list[str] = []

        if gate_result.decision == PromotionDecisionType.BLOCK:
            reasons.append(
                f"Blocked by gate rules: {', '.join(gate_result.violations)}"
            )
            decision = PromotionDecisionType.BLOCK
        elif gate_result.decision == PromotionDecisionType.REVIEW:
            reasons.append(
                f"Review required due to warnings: {', '.join(gate_result.warnings)}"
            )
            decision = PromotionDecisionType.REVIEW
        else:
            reasons.append("All gate checks passed. Promoted artifacts.")
            decision = PromotionDecisionType.PASS
            artifact_ids = [
                ArtifactCandidate.generate_candidate_id(
                    c.candidate_id, "promoted", c.hash
                ).replace("ACAND-", "ART-")
                for c in candidates
            ]

        return PromotionDecision(
            decision=decision,
            artifact_ids=artifact_ids,
            reasons=reasons,
            policy_version=policy_version,
        )
