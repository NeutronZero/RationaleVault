from rationalevault.canonical import (
    CanonicalEnvelope,
    CanonicalPayload,
    CanonicalSerializer,
    CanonicalTimestamp,
    StableIdGenerator,
    EventType,
)


def test_public_api_exports():
    assert CanonicalEnvelope is not None
    assert CanonicalPayload is not None
    assert CanonicalSerializer is not None
    assert CanonicalTimestamp is not None
    assert StableIdGenerator is not None
    assert EventType is not None
