import pytest

from rationalevault.canonical.payload import CanonicalPayload


def test_payload_from_dict():
    p = CanonicalPayload.from_dict({"key": "value"})
    assert p.data == {"key": "value"}


def test_payload_to_dict():
    p = CanonicalPayload(data={"key": "value"})
    assert p.to_dict() == {"key": "value"}


def test_payload_canonicalize_sorts_keys():
    p = CanonicalPayload(data={"z": 1, "a": 2})
    c = p.canonicalize()
    assert list(c.data.keys()) == ["a", "z"]


def test_payload_canonicalize_normalizes_unicode():
    p = CanonicalPayload(data={"key": "caf\u0065\u0301"})
    c = p.canonicalize()
    assert c.data["key"] == "caf\u00e9"


def test_payload_validate_missing_required():
    p = CanonicalPayload(data={"extra": "value"})
    with pytest.raises(ValueError, match="Missing"):
        p.validate(required={"key"})


def test_payload_validate_rejects_reserved_namespace():
    p = CanonicalPayload(data={"meta": {"version": 1}})
    with pytest.raises(ValueError, match="Reserved"):
        p.validate()


def test_payload_immutable():
    p = CanonicalPayload(data={"key": "value"})
    with pytest.raises(AttributeError):
        p.data = {}
