"""CLI handler for `rv recommendation` subcommands.

Foreign imports are deferred to avoid startup overhead when
recommendation features are not used.
"""
from __future__ import annotations

import argparse
import sys


def cmd_recommendation(args: argparse.Namespace) -> None:
    """Handle `rv recommendation` subcommands."""
    if args.recommendation_command == "show":
        _cmd_recommendation_show(args)
    else:
        print(
            f"Error: Unknown recommendation command "
            f"'{args.recommendation_command}'",
        )
        sys.exit(1)


def _cmd_recommendation_show(args: argparse.Namespace) -> None:
    """Show recommendations."""
    from datetime import datetime

    from rationalevault.recommendation.projection import (
        RecommendationProjection,
    )
    from rationalevault.recommendation.runtime import (
        RecommendationRuntime,
    )
    from rationalevault.recommendation.state import (
        RecommendationQueryContext, RecommendationState,
    )

    proj = RecommendationProjection()
    runtime = RecommendationRuntime()

    try:
        from rationalevault.knowledge.factory import (
            get_knowledge_provider,
        )
        knowledge_provider = get_knowledge_provider()
        knowledge = knowledge_provider.get_all_knowledge()

        events = []
        for k in knowledge:
            from rationalevault.schema.events import (
                EventRecord, EventType, EventMetadata,
            )
            from uuid import uuid4

            events.append(EventRecord(
                event_sequence=len(events) + 1,
                id=uuid4(),
                project_id=uuid4(),
                stream_id="knowledge",
                version=1,
                event_type=EventType.KNOWLEDGE_CREATED,
                metadata=EventMetadata(
                    actor="cli", source="recommendation",
                ),
                payload={
                    "knowledge_id": k.id,
                    "title": k.title,
                    "content": k.content,
                    "knowledge_type": k.knowledge_type.value,
                    "tags": k.tags,
                    "importance": k.importance,
                    "knowledge_domain": k.knowledge_domain.value,
                },
                parent_id=None,
                recorded_at=None,
            ))

        state = (
            proj.reduce(events) if events else RecommendationState()
        )
    except Exception:
        state = RecommendationState()

    entity = getattr(args, "for", None)
    category_filter = getattr(args, "category", None)

    cat = None
    if category_filter:
        from rationalevault.recommendation.state import (
            RecommendationCategory,
        )
        try:
            cat = RecommendationCategory(category_filter)
        except ValueError:
            print(
                f"Error: Unknown category '{category_filter}'",
            )
            sys.exit(1)

    limit = getattr(args, "limit", 10)
    ctx = RecommendationQueryContext(query_time=datetime.now())

    results = runtime.search(
        state,
        entity=entity,
        category=cat,
        k=limit,
        context=ctx,
    )

    fmt = getattr(args, "format", "table")
    if fmt == "json":
        import json
        output = [
            {
                "id": r.recommendation.id,
                "rule_id": r.recommendation.rule_id,
                "rule_version": r.recommendation.rule_version,
                "target_entity": r.recommendation.target_entity,
                "category": r.recommendation.category.value,
                "priority": r.recommendation.priority,
                "final_score": r.final_score,
                "rationale": r.recommendation.rationale,
                "evidence": [
                    e.sequence
                    for e in r.recommendation.evidence
                ],
            }
            for r in results
        ]
        print(json.dumps(output, indent=2))
    else:
        if not results:
            print("No recommendations found.")
            return

        print(
            f"Recommendations "
            f"({len(results)} of {state.recommendation_count})",
        )
        print("=" * 70)

        for r in results:
            rec = r.recommendation
            cat_str = rec.category.value.upper()
            print(
                f"  [{cat_str:<14}] "
                f"priority={rec.priority:.2f} "
                f"score={r.final_score:.2f} "
                f"| {rec.rationale}",
            )
            print(
                f"    rule={rec.rule_id} v{rec.rule_version} "
                f"target={rec.target_entity}",
            )

        print("=" * 70)
