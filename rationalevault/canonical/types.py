"""Shared types for canonical representation — immutable enums."""

from __future__ import annotations

import enum


class EventType(enum.StrEnum):
    """Registered event types for replay dispatch.

    Immutable — no runtime mutation allowed.
    For extensibility, define new members in future versions.
    """

    DECISION_RECORDED = "decision_recorded"
    EVALUATION_RECORDED = "evaluation_recorded"
    KNOWLEDGE_UPDATED = "knowledge_updated"
    EXPERIENCE_RECORDED = "experience_recorded"
    OUTCOME_OBSERVED = "outcome_observed"
