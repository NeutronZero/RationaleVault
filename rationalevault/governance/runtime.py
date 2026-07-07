"""Governance Runtime and Evidence Provider implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from rationalevault.projection_platform.models import DependencyKind
from rationalevault.governance.state import (
    GovernanceRule,
    GovernanceState,
    GovernanceWarning,
    RuleEvaluation,
)
from rationalevault.recommendation.state import RecommendationState, Recommendation


@dataclass(frozen=True)
class GovernanceEvidence:
    """Evidence collected from dependencies for policy evaluation."""

    recommendations: list[Recommendation] = field(default_factory=list)


@runtime_checkable
class GovernanceEvidenceProvider(Protocol):
    """Protocol for collecting evidence matching policy conditions."""

    def collect(self, rule: GovernanceRule) -> GovernanceEvidence:
        """Collect matching evidence from projections."""
        ...


class DefaultEvidenceProvider:
    """Default implementation of GovernanceEvidenceProvider using DependencyReader."""

    def __init__(self, dependency_reader: Any | None = None) -> None:
        self._reader = dependency_reader

    def collect(self, rule: GovernanceRule) -> GovernanceEvidence:
        if self._reader is None:
            return GovernanceEvidence()

        try:
            rec_state = self._reader.get("recommendation")
            if not rec_state or not isinstance(rec_state, RecommendationState):
                return GovernanceEvidence()
        except Exception:
            return GovernanceEvidence()

        matches = []
        for rec in rec_state.recommendations:
            # Check condition
            cond = rule.condition
            if cond.categories is not None and rec.category not in cond.categories:
                continue
            if cond.minimum_priority is not None and rec.priority < cond.minimum_priority:
                continue
            matches.append(rec)

        return GovernanceEvidence(recommendations=matches)


class GovernanceRuntime:
    """Runtime evaluation engine for governance warnings."""

    def evaluate_rules(
        self,
        state: GovernanceState,
        provider: GovernanceEvidenceProvider,
    ) -> list[RuleEvaluation]:
        evaluations = []
        for rule in state.rules:
            if not rule.enabled:
                continue

            evidence = provider.collect(rule)
            matched_recs = evidence.recommendations

            matched = len(matched_recs) > 0
            matched_entities = list({r.target_entity for r in matched_recs})
            
            # Supporting event sequences as evidence
            event_sequences = []
            for r in matched_recs:
                for ev in r.evidence:
                    event_sequences.append(ev.sequence)
            event_sequences = sorted(list(set(event_sequences)))

            message = ""
            if matched:
                message = (
                    f"Policy rule '{rule.metadata.id}' matched with "
                    f"{len(matched_recs)} recommendations across "
                    f"{len(matched_entities)} entities."
                )

            evaluations.append(
                RuleEvaluation(
                    rule_id=rule.metadata.id,
                    rule_version=rule.metadata.version,
                    matched=matched,
                    matched_entities=matched_entities,
                    evidence=event_sequences,
                    message=message,
                )
            )

        return evaluations

    def generate_warnings(
        self,
        state: GovernanceState,
        evaluations: list[RuleEvaluation],
        projection_version: int = 1,
        query_time: datetime | None = None,
    ) -> list[GovernanceWarning]:
        if query_time is None:
            query_time = datetime.now()

        # Build rule lookup
        rules_by_key = {(r.metadata.id, r.metadata.version): r for r in state.rules}

        warnings = []
        for ev in evaluations:
            if not ev.matched:
                continue

            rule = rules_by_key.get((ev.rule_id, ev.rule_version))
            if not rule:
                continue

            for entity in ev.matched_entities:
                triggering_seq = ev.evidence[0] if ev.evidence else 0
                warning_id = GovernanceWarning.make_id(
                    projection_version,
                    rule.metadata.id,
                    rule.metadata.version,
                    entity,
                    triggering_seq,
                )
                warnings.append(
                    GovernanceWarning(
                        id=warning_id,
                        rule_id=rule.metadata.id,
                        rule_version=rule.metadata.version,
                        target_entity=entity,
                        severity=rule.metadata.severity,
                        action=rule.metadata.action,
                        message=ev.message,
                        evidence=ev.evidence,
                        created_at=query_time,
                    )
                )

        return warnings

    def search(
        self,
        warnings: list[GovernanceWarning],
        severity: Any | None = None,
        action: Any | None = None,
        limit: int = 100,
    ) -> list[GovernanceWarning]:
        results = warnings

        if severity is not None:
            results = [w for w in results if w.severity == severity]

        if action is not None:
            results = [w for w in results if w.action == action]

        return results[:limit]
