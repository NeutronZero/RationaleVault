"""
RationaleVault Reflection Event Payloads — Immutable event-sourced contracts for the reflection event hierarchy.

Every reflection event follows:

    Domain Object → Event Payload → Event Ledger → Projection → State

Design rules:
  - Payloads are FROZEN dataclasses, never reused as domain objects.
  - Every payload includes schema_version for forward compatibility.
  - Domain models (Reflection, ReflectionCandidate) remain separate.
  - Payloads are the CONTRACT; domain objects are implementation details.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any



# =====================================================================
# Base
# =====================================================================

SCHEMA_VERSION = "1.0"


# =====================================================================
# Rule Traces (shared by assessed and traced payloads)
# =====================================================================

@dataclass(frozen=True)
class RuleResultPayload:
    """Result of a single rule evaluation. Used in REFLECTION_ASSESSED."""
    rule_name: str
    passed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "passed": self.passed,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RuleResultPayload:
        return cls(
            rule_name=d["rule_name"],
            passed=d["passed"],
            reason=d["reason"],
        )


@dataclass(frozen=True)
class RuleTracePayload:
    """Detailed rule trace. Used in REFLECTION_TRACED."""
    rule_name: str
    passed: bool
    reason: str
    inputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "passed": self.passed,
            "reason": self.reason,
            "inputs": self.inputs,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RuleTracePayload:
        return cls(
            rule_name=d["rule_name"],
            passed=d["passed"],
            reason=d["reason"],
            inputs=d.get("inputs", {}),
        )


# =====================================================================
# Event Payloads
# =====================================================================

@dataclass(frozen=True)
class ReflectionCandidateCreatedPayload:
    """
    Emitted when a ReflectionCandidate is created from learning records.

    Event: REFLECTION_CANDIDATE_CREATED
    """
    schema_version: str = SCHEMA_VERSION
    candidate_id: str = ""           # RCAND-[hash]
    source_artifact_id: str = ""
    reason: str = ""                 # ReflectionReason value
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    config_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "source_artifact_id": self.source_artifact_id,
            "reason": self.reason,
            "context": self.context,
            "created_at": self.created_at,
            "config_version": self.config_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReflectionCandidateCreatedPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            candidate_id=d["candidate_id"],
            source_artifact_id=d["source_artifact_id"],
            reason=d["reason"],
            context=d.get("context", {}),
            created_at=d["created_at"],
            config_version=d["config_version"],
        )


@dataclass(frozen=True)
class ReflectionAssessedPayload:
    """
    Emitted when a ReflectionCandidate has been evaluated by the rule engine.

    Event: REFLECTION_ASSESSED
    """
    schema_version: str = SCHEMA_VERSION
    assessment_id: str = ""
    candidate_id: str = ""           # RCAND-[hash]
    approved: bool = False
    confidence: float = 0.0
    base_confidence: float = 0.0
    recurrence_score: float = 0.0
    contradiction_penalty: float = 0.0
    duplicate_suppressed: bool = False
    rules_evaluated: list[RuleResultPayload] = field(default_factory=list)
    supporting_record_ids: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assessment_id": self.assessment_id,
            "candidate_id": self.candidate_id,
            "approved": self.approved,
            "confidence": round(self.confidence, 4),
            "base_confidence": round(self.base_confidence, 4),
            "recurrence_score": round(self.recurrence_score, 4),
            "contradiction_penalty": round(self.contradiction_penalty, 4),
            "duplicate_suppressed": self.duplicate_suppressed,
            "rules_evaluated": [r.to_dict() for r in self.rules_evaluated],
            "supporting_record_ids": self.supporting_record_ids,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReflectionAssessedPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            assessment_id=d["assessment_id"],
            candidate_id=d["candidate_id"],
            approved=d["approved"],
            confidence=d["confidence"],
            base_confidence=d["base_confidence"],
            recurrence_score=d["recurrence_score"],
            contradiction_penalty=d["contradiction_penalty"],
            duplicate_suppressed=d["duplicate_suppressed"],
            rules_evaluated=[RuleResultPayload.from_dict(r) for r in d.get("rules_evaluated", [])],
            supporting_record_ids=d.get("supporting_record_ids", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class ReflectionGeneratedPayload:
    """
    Emitted when a Reflection is compiled from an approved assessment.

    Event: REFLECTION_GENERATED
    """
    schema_version: str = SCHEMA_VERSION
    reflection_id: str = ""          # REFL-[hash]
    candidate_id: str = ""           # RCAND-[hash]
    status: str = ""                 # ReflectionStatus value
    insights: list[str] = field(default_factory=list)
    reconstructed_rationale: str = ""
    actionable_guidelines: list[str] = field(default_factory=list)
    source_learning_record_ids: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "reflection_id": self.reflection_id,
            "candidate_id": self.candidate_id,
            "status": self.status,
            "insights": self.insights,
            "reconstructed_rationale": self.reconstructed_rationale,
            "actionable_guidelines": self.actionable_guidelines,
            "source_learning_record_ids": self.source_learning_record_ids,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReflectionGeneratedPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            reflection_id=d["reflection_id"],
            candidate_id=d["candidate_id"],
            status=d["status"],
            insights=d.get("insights", []),
            reconstructed_rationale=d.get("reconstructed_rationale", ""),
            actionable_guidelines=d.get("actionable_guidelines", []),
            source_learning_record_ids=d.get("source_learning_record_ids", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class ReflectionTracedPayload:
    """
    Emitted when a ReflectionTrace is produced (audit trail for why a reflection
    was approved or rejected).

    Event: REFLECTION_TRACED
    """
    schema_version: str = SCHEMA_VERSION
    trace_id: str = ""               # RTRC-[hash]
    reflection_id: str = ""          # REFL-[hash] (or RCAND-[hash] if rejected)
    candidate_id: str = ""           # RCAND-[hash]
    approved: bool = False
    confidence: float = 0.0
    rules_fired: list[RuleTracePayload] = field(default_factory=list)
    contributing_learning_records: list[str] = field(default_factory=list)
    ignored_learning_records: list[str] = field(default_factory=list)
    duplicate_suppressed: bool = False
    conflict_resolution: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "reflection_id": self.reflection_id,
            "candidate_id": self.candidate_id,
            "approved": self.approved,
            "confidence": round(self.confidence, 4),
            "rules_fired": [r.to_dict() for r in self.rules_fired],
            "contributing_learning_records": self.contributing_learning_records,
            "ignored_learning_records": self.ignored_learning_records,
            "duplicate_suppressed": self.duplicate_suppressed,
            "conflict_resolution": self.conflict_resolution,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReflectionTracedPayload:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            trace_id=d["trace_id"],
            reflection_id=d["reflection_id"],
            candidate_id=d["candidate_id"],
            approved=d["approved"],
            confidence=d["confidence"],
            rules_fired=[RuleTracePayload.from_dict(r) for r in d.get("rules_fired", [])],
            contributing_learning_records=d.get("contributing_learning_records", []),
            ignored_learning_records=d.get("ignored_learning_records", []),
            duplicate_suppressed=d.get("duplicate_suppressed", False),
            conflict_resolution=d.get("conflict_resolution"),
            created_at=d["created_at"],
        )


# =====================================================================
# ID Generation
# =====================================================================

def generate_reflection_trace_id(reflection_id: str, candidate_id: str, created_at: str) -> str:
    """Generate deterministic RTRC-[hash] identifier."""
    data = f"trace:{reflection_id}:{candidate_id}:{created_at}"
    h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
    return f"RTRC-{h}"


def generate_assessment_id(candidate_id: str, created_at: str) -> str:
    """Generate deterministic ASSESSMENT-[hash] identifier for payloads."""
    data = f"reflection_assessment:{candidate_id}:{created_at}"
    h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
    return f"RASSMT-{h}"
