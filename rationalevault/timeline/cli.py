"""CLI handler for `rv timeline` subcommands.

Foreign imports are deferred to avoid startup overhead when timeline
features are not used.
"""
from __future__ import annotations

import argparse
import sys


def cmd_timeline(args: argparse.Namespace) -> None:
    """Handle `rv timeline` subcommands."""
    if args.timeline_command == "show":
        _cmd_timeline_show(args)
    else:
        print(f"Error: Unknown timeline command '{args.timeline_command}'")
        sys.exit(1)


def _cmd_timeline_show(args: argparse.Namespace) -> None:
    """Show chronological narrative entries."""
    from rationalevault.timeline.projection import TimelineProjection
    from rationalevault.timeline.state import TimelineState

    proj = TimelineProjection()

    # Build timeline from knowledge events
    try:
        from rationalevault.knowledge.factory import get_knowledge_provider
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
                metadata=EventMetadata(actor="cli", source="timeline"),
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

        state = proj.reduce(events) if events else TimelineState()
    except Exception:
        state = TimelineState()

    # Apply filters
    entries = state.entries

    category_filter = getattr(args, "category", None)
    if category_filter:
        from rationalevault.timeline.state import TimelineCategory
        try:
            cat = TimelineCategory(category_filter)
            entries = [e for e in entries if e.category == cat]
        except ValueError:
            print(f"Error: Unknown category '{category_filter}'")
            print(f"Valid categories: {', '.join(c.value for c in TimelineCategory)}")
            sys.exit(1)

    limit = getattr(args, "limit", 50)
    entries = entries[-limit:]

    # Output
    fmt = getattr(args, "format", "table")
    if fmt == "json":
        import json
        output = [
            {
                "sequence": e.sequence,
                "event_type": e.event_type.value,
                "category": e.category.value,
                "actor": e.actor,
                "subject_entity": e.subject_entity,
                "summary": e.summary,
            }
            for e in entries
        ]
        print(json.dumps(output, indent=2))
    else:
        if not entries:
            print("No timeline entries found.")
            return

        print(f"Timeline ({len(entries)} entries, {state.entry_count} total)")
        print("=" * 70)

        for e in entries:
            cat = e.category.value.upper()
            actor = f" [{e.actor}]" if e.actor else ""
            print(f"  {e.sequence:4d} | {cat:<10} | {e.summary}{actor}")

        print("=" * 70)
