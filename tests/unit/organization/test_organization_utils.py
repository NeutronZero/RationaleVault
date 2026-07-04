"""Unit tests for organization utility functions."""
from __future__ import annotations

from datetime import datetime, timezone
from rationalevault.organization.utils import resolve_compiled_at


def test_resolve_compiled_at() -> None:
    ref = datetime(2026, 7, 2, 12, 0, 0, tzinfo=timezone.utc)
    assert resolve_compiled_at(ref) == ref.isoformat()

    now_str = resolve_compiled_at(None)
    assert datetime.fromisoformat(now_str) is not None
