"""Common utilities for RationaleVault projections."""
from __future__ import annotations

from datetime import datetime, timezone


def resolve_compiled_at(reference_time: datetime | None) -> str:
    """Helper to resolve compiled_at timestamp.

    If reference_time is provided, return its ISO format.
    Otherwise, return the current UTC timestamp in ISO format.
    """
    if reference_time is not None:
        return reference_time.isoformat()
    return datetime.now(timezone.utc).isoformat()
