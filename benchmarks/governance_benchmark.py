"""Governance Projection Benchmarks.

Measures policy evaluation speed, warnings emission, and evidence scale metrics.
"""

from __future__ import annotations

import time
from uuid import uuid4
from datetime import datetime

from rationalevault.governance.projection import GovernanceProjection
from rationalevault.governance.runtime import GovernanceRuntime, DefaultEvidenceProvider
from rationalevault.governance.state import (
    GovernanceAction,
    GovernanceCondition,
    GovernanceRule,
    GovernanceRuleMetadata,
    GovernanceSeverity,
    GovernanceState,
)
from rationalevault.recommendation.state import Recommendation, RecommendationCategory, RecommendationState
from rationalevault.schema.events import EventMetadata, EventRecord, EventType
from rationalevault.projection_platform.context import DependencyReader


def _event(event_type: EventType, payload: dict, seq: int) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid4(),
        project_id=uuid4(),
        stream_id="governance",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="bench", source="bench"),
        payload=payload,
        parent_id=None,
        recorded_at=datetime.now(),
    )


def generate_governance_rules(count: int) -> list[GovernanceRule]:
    rules = []
    for i in range(count):
        severity = GovernanceSeverity.WARNING if i % 2 == 0 else GovernanceSeverity.CRITICAL
        action = GovernanceAction.NOTIFY if i % 2 == 0 else GovernanceAction.BLOCK
        categories = {RecommendationCategory.RISK} if i % 3 == 0 else {RecommendationCategory.KNOWLEDGE_GAP}
        
        rules.append(
            GovernanceRule(
                metadata=GovernanceRuleMetadata(
                    id=f"rule_{i}",
                    version=1,
                    description=f"Policy rule benchmark {i}",
                    severity=severity,
                    action=action,
                ),
                condition=GovernanceCondition(
                    categories=categories,
                    minimum_priority=0.5,
                ),
            )
        )
    return rules


def generate_recommendations(count: int) -> list[Recommendation]:
    recs = []
    for i in range(count):
        category = RecommendationCategory.RISK if i % 2 == 0 else RecommendationCategory.KNOWLEDGE_GAP
        priority = 0.4 + (i % 6) * 0.1  # 0.4 to 0.9

        from rationalevault.recommendation.state import EvidenceReference
        recs.append(
            Recommendation(
                id=f"rec_{i}",
                rule_id=f"rule_{i}",
                rule_version=1,
                target_entity=f"entity_{i}",
                category=category,
                priority=priority,
                rationale=f"Simulated recommendation {i}",
                evidence=[EvidenceReference(sequence=i)],
            )
        )
    return recs


def run_benchmarks() -> None:
    print("=" * 70)
    print("Governance Policy Evaluation Benchmarks")
    print("=" * 70)

    # Setup rule states & simulated recommendations
    rule_counts = [10, 50, 100, 500]
    rec_count = 1000

    recs = generate_recommendations(rec_count)
    rec_state = RecommendationState(recommendations=recs, sequence=rec_count)
    
    reader = DependencyReader()
    reader.set("recommendation", rec_state)
    provider = DefaultEvidenceProvider(reader)
    runtime = GovernanceRuntime()

    print(f"\nEvaluating policy engine against {rec_count} recommendations:")
    print(
        f"{'Rules':>8} {'Matched':>8} {'Warnings':>10} "
        f"{'Eval Time':>12} {'Avg Ev Size':>12}"
    )

    for rc in rule_counts:
        rules = generate_governance_rules(rc)
        state = GovernanceState(rules=rules, sequence=rc)

        start = time.perf_counter()
        evals = runtime.evaluate_rules(state, provider)
        warnings = runtime.generate_warnings(state, evals)
        eval_ms = (time.perf_counter() - start) * 1000

        matched_count = sum(1 for ev in evals if ev.matched)
        warnings_count = len(warnings)
        
        evidence_sizes = [len(ev.evidence) for ev in evals if ev.matched]
        avg_ev_size = sum(evidence_sizes) / len(evidence_sizes) if evidence_sizes else 0.0

        print(
            f"{rc:>8} {matched_count:>8} {warnings_count:>10} "
            f"{eval_ms:>11.2f}ms {avg_ev_size:>11.1f}"
        )

    print("=" * 70)


if __name__ == "__main__":
    run_benchmarks()
