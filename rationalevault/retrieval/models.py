"""RationaleVault Retrieval Models — Types for hybrid retrieval orchestration.

RetrievalPlan = RetrievalOrchestrator.build_plan(query, project_id, available_projections)

Ephemeral planning output. Not stored. Not projected. Not primary state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RetrievalIntent(Enum):
    """Classifies what the query is asking for."""
    CONTINUATION = "continuation"
    KNOWLEDGE_QUERY = "knowledge_query"
    IMPACT_ANALYSIS = "impact_analysis"
    CROSS_PROJECT = "cross_project"
    ORGANIZATIONAL = "organizational"
    GENERAL = "general"


from types import MappingProxyType

# Intent → projections it activates
INTENT_PROJECTION_MAP: MappingProxyType[RetrievalIntent, frozenset[str]] = MappingProxyType({
    RetrievalIntent.CONTINUATION: frozenset({"continuation", "knowledge", "graph", "cross_project", "organization", "organization_graph"}),
    RetrievalIntent.KNOWLEDGE_QUERY: frozenset({"knowledge", "graph"}),
    RetrievalIntent.IMPACT_ANALYSIS: frozenset({"knowledge", "graph", "cross_project", "organization", "organization_graph"}),
    RetrievalIntent.CROSS_PROJECT: frozenset({"cross_project", "organization"}),
    RetrievalIntent.ORGANIZATIONAL: frozenset({"organization", "organization_graph"}),
    RetrievalIntent.GENERAL: frozenset({"knowledge"}),
})

# Intent → base context weights
INTENT_WEIGHT_MAP: MappingProxyType[RetrievalIntent, MappingProxyType[str, float]] = MappingProxyType({
    RetrievalIntent.CONTINUATION: MappingProxyType({
        "continuation": 0.30, "knowledge": 0.20, "graph": 0.20,
        "cross_project": 0.10, "organization": 0.10, "organization_graph": 0.10,
    }),
    RetrievalIntent.KNOWLEDGE_QUERY: MappingProxyType({
        "continuation": 0.10, "knowledge": 0.50, "graph": 0.30,
        "cross_project": 0.05, "organization": 0.05, "organization_graph": 0.00,
    }),
    RetrievalIntent.IMPACT_ANALYSIS: MappingProxyType({
        "continuation": 0.00, "knowledge": 0.25, "graph": 0.30,
        "cross_project": 0.10, "organization": 0.10, "organization_graph": 0.25,
    }),
    RetrievalIntent.CROSS_PROJECT: MappingProxyType({
        "continuation": 0.00, "knowledge": 0.20, "graph": 0.10,
        "cross_project": 0.40, "organization": 0.25, "organization_graph": 0.05,
    }),
    RetrievalIntent.ORGANIZATIONAL: MappingProxyType({
        "continuation": 0.00, "knowledge": 0.10, "graph": 0.05,
        "cross_project": 0.20, "organization": 0.30, "organization_graph": 0.35,
    }),
    RetrievalIntent.GENERAL: MappingProxyType({
        "continuation": 0.00, "knowledge": 1.00, "graph": 0.00,
        "cross_project": 0.00, "organization": 0.00, "organization_graph": 0.00,
    }),
})

# Intent trigger keywords
INTENT_KEYWORDS: MappingProxyType[RetrievalIntent, frozenset[str]] = MappingProxyType({
    RetrievalIntent.CONTINUATION: frozenset({
        "continue", "resume", "where", "left", "off", "last", "session",
        "sprint", "working", "doing", "status", "progress", "active",
        "blocked", "stalled", "changed", "recent", "priority", "urgent",
        "attention", "next", "action", "inactive",
    }),
    RetrievalIntent.IMPACT_ANALYSIS: frozenset({
        "impact", "break", "change", "affect", "depend", "cascade",
        "consequence", "ripple", "blast", "radius", "producer",
        "consumer", "downstream", "upstream",
    }),
    RetrievalIntent.CROSS_PROJECT: frozenset({
        "transfer", "shared", "across", "other", "projects", "reusable",
        "mobile", "portable",
    }),
    RetrievalIntent.ORGANIZATIONAL: frozenset({
        "org", "organization", "flow", "lineage", "adoption", "cluster",
        "enterprise", "company", "project", "producer", "consumer",
        "hotspot", "graph", "blast", "radius", "centrality",
    }),
    RetrievalIntent.KNOWLEDGE_QUERY: frozenset({
        "knowledge", "principle", "invariant", "synthesized", "decision",
        "architecture", "lesson", "pattern",
    }),
    RetrievalIntent.GENERAL: frozenset(),
})

_WEIGHT_EPSILON = 0.02


@dataclass
class RetrievalPlan:
    """Ephemeral planning output for hybrid retrieval.

    Not stored. Not projected. Not primary state.
    Projection-agnostic: future projections require no schema migration.
    """
    primary_intent: RetrievalIntent
    matched_intents: list[RetrievalIntent] = field(default_factory=list)
    projections: dict[str, bool] = field(default_factory=dict)
    context_weights: dict[str, float] = field(default_factory=dict)
    requested_projections: dict[str, bool] = field(default_factory=dict)
    confidence: float = 0.5
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate weight normalization."""
        total = sum(self.context_weights.values())
        if self.context_weights and abs(total - 1.0) > _WEIGHT_EPSILON:
            # Auto-normalize
            if total > 0:
                self.context_weights = {k: v / total for k, v in self.context_weights.items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_intent": self.primary_intent.value,
            "matched_intents": [i.value for i in self.matched_intents],
            "projections": self.projections,
            "context_weights": {k: round(v, 4) for k, v in self.context_weights.items()},
            "requested_projections": self.requested_projections,
            "confidence": round(self.confidence, 4),
            "reasons": self.reasons,
        }


@dataclass
class OrchestrationEvalResult:
    """Evaluation result for retrieval orchestration quality."""
    intent_accuracy: float = 0.0
    projection_selection_accuracy: float = 0.0
    projection_efficiency: float = 0.0
    context_weight_accuracy: float = 0.0
    determinism: float = 0.0
    availability_handling_accuracy: float = 0.0

    def passes_exit_gate(self) -> tuple[bool, list[str]]:
        """Check if all metrics pass thresholds."""
        from rationalevault.evaluation.thresholds import EvaluationThresholds
        t = EvaluationThresholds()
        failures: list[str] = []

        checks = {
            "intent_accuracy": (self.intent_accuracy, t.MIN_I12_INTENT_ACCURACY),
            "projection_selection_accuracy": (self.projection_selection_accuracy, t.MIN_I12_PROJECTION_SELECTION),
            "projection_efficiency": (self.projection_efficiency, t.MIN_I12_PROJECTION_EFFICIENCY),
            "context_weight_accuracy": (self.context_weight_accuracy, t.MIN_I12_CONTEXT_WEIGHT_ACCURACY),
            "determinism": (self.determinism, t.MIN_I12_DETERMINISM),
            "availability_handling_accuracy": (self.availability_handling_accuracy, t.MIN_I12_AVAILABILITY_HANDLING),
        }

        for name, (value, threshold) in checks.items():
            if value < threshold:
                failures.append(name)

        return len(failures) == 0, failures

    def to_dict(self) -> dict[str, Any]:
        passed, failures = self.passes_exit_gate()
        from rationalevault.evaluation.thresholds import EvaluationThresholds
        t = EvaluationThresholds()
        checks = {
            "intent_accuracy": self.intent_accuracy,
            "projection_selection_accuracy": self.projection_selection_accuracy,
            "projection_efficiency": self.projection_efficiency,
            "context_weight_accuracy": self.context_weight_accuracy,
            "determinism": self.determinism,
            "availability_handling_accuracy": self.availability_handling_accuracy,
        }
        threshold_map = {
            "intent_accuracy": t.MIN_I12_INTENT_ACCURACY,
            "projection_selection_accuracy": t.MIN_I12_PROJECTION_SELECTION,
            "projection_efficiency": t.MIN_I12_PROJECTION_EFFICIENCY,
            "context_weight_accuracy": t.MIN_I12_CONTEXT_WEIGHT_ACCURACY,
            "determinism": t.MIN_I12_DETERMINISM,
            "availability_handling_accuracy": t.MIN_I12_AVAILABILITY_HANDLING,
        }
        total = len(checks)
        passing = sum(1 for name, value in checks.items() if value >= threshold_map[name])
        return {
            **checks,
            "retrieval_orchestration_success_rate": passing / total if total > 0 else 1.0,
            "passed": passed,
            "failures": failures,
        }
