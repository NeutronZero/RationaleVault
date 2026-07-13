from datetime import datetime, timezone

import pytest

from rationalevault.canonical.id_generator import StableIdGenerator
from rationalevault.canonical.timestamp import CanonicalTimestamp


def _ts() -> CanonicalTimestamp:
    return CanonicalTimestamp.from_datetime(
        datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    )


def test_event_id_format():
    eid = StableIdGenerator.generate_event_id("EXP-abc", "decision_recorded", 1, _ts())
    assert eid.startswith("EVT-")
    assert len(eid) == 4 + 12  # "EVT-" + 12 hex chars


def test_experience_id_format():
    xid = StableIdGenerator.generate_experience_id("agent-001", "project-42", _ts())
    assert xid.startswith("EXP-")
    assert len(xid) == 4 + 12  # "EXP-" + 12 hex chars


def test_event_id_deterministic():
    args = ("EXP-abc", "decision_recorded", 1, _ts())
    assert StableIdGenerator.generate_event_id(*args) == StableIdGenerator.generate_event_id(*args)


def test_experience_id_deterministic():
    args = ("agent-001", "project-42", _ts())
    assert StableIdGenerator.generate_experience_id(*args) == StableIdGenerator.generate_experience_id(*args)


def test_event_id_changes_with_input():
    args1 = ("EXP-abc", "decision_recorded", 1, _ts())
    args2 = ("EXP-abc", "decision_recorded", 2, _ts())
    assert StableIdGenerator.generate_event_id(*args1) != StableIdGenerator.generate_event_id(*args2)


def test_experience_id_changes_with_input():
    args1 = ("agent-001", "project-42", _ts())
    args2 = ("agent-002", "project-42", _ts())
    assert StableIdGenerator.generate_experience_id(*args1) != StableIdGenerator.generate_experience_id(*args2)
