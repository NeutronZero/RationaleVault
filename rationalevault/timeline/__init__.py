"""Timeline Projection — narrative chronological view of system evolution."""

from rationalevault.timeline.normalizer import normalize_event, render_summary
from rationalevault.timeline.projection import TimelineProjection
from rationalevault.timeline.state import TimelineCategory, TimelineEntry, TimelineState

__all__ = [
    "TimelineCategory",
    "TimelineEntry",
    "TimelineProjection",
    "TimelineState",
    "normalize_event",
    "render_summary",
]
