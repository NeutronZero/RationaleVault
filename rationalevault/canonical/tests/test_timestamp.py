from datetime import datetime, timezone, timedelta

import pytest

from rationalevault.canonical.timestamp import CanonicalTimestamp


def test_timestamp_from_datetime_utc():
    dt = datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    ts = CanonicalTimestamp.from_datetime(dt)
    assert ts.to_iso8601() == "2026-07-13T14:35:42.123456Z"


def test_timestamp_from_datetime_converts_to_utc():
    est = timezone(timedelta(hours=-5))
    dt = datetime(2026, 7, 13, 9, 35, 42, 123456, tzinfo=est)
    ts = CanonicalTimestamp.from_datetime(dt)
    assert ts.to_iso8601() == "2026-07-13T14:35:42.123456Z"


def test_timestamp_from_naive_raises():
    dt = datetime(2026, 7, 13, 14, 35, 42, 123456)
    with pytest.raises(ValueError, match="timezone-aware"):
        CanonicalTimestamp.from_datetime(dt)


def test_timestamp_from_iso8601():
    ts = CanonicalTimestamp.from_iso8601("2026-07-13T14:35:42.123456Z")
    assert ts.to_iso8601() == "2026-07-13T14:35:42.123456Z"


def test_timestamp_to_dict():
    dt = datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    ts = CanonicalTimestamp.from_datetime(dt)
    assert ts.to_dict() == "2026-07-13T14:35:42.123456Z"


def test_timestamp_to_datetime():
    dt = datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    ts = CanonicalTimestamp.from_datetime(dt)
    assert ts.to_datetime() == dt


def test_timestamp_immutable():
    dt = datetime(2026, 7, 13, 14, 35, 42, 123456, tzinfo=timezone.utc)
    ts = CanonicalTimestamp.from_datetime(dt)
    with pytest.raises(AttributeError):
        ts.value = datetime.now(timezone.utc)
