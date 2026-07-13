from rationalevault.canonical.specification import (
    RVCJ_VERSION,
    EVENT_SCHEMA_VERSION,
    KEY_ORDERING,
    UNICODE_NORMALIZATION,
    TIMESTAMP_FORMAT,
    TIMESTAMP_PRECISION,
    DECIMAL_POLICY,
    BINARY_ENCODING,
    NULL_SEMANTICS,
    HASH_ALGORITHM,
    HASH_DISPLAY_LENGTH,
    HASH_INTERNAL_LENGTH,
    RESERVED_PAYLOAD_NAMESPACES,
)


def test_rvcj_version_is_one():
    assert RVCJ_VERSION == 1


def test_event_schema_version_is_one():
    assert EVENT_SCHEMA_VERSION == 1


def test_key_ordering_is_lexicographic():
    assert KEY_ORDERING == "lexicographic"


def test_unicode_normalization_is_nfc():
    assert UNICODE_NORMALIZATION == "NFC"


def test_timestamp_format_is_rfc3339_utc():
    assert TIMESTAMP_FORMAT == "RFC3339-UTC"


def test_timestamp_precision_is_microsecond():
    assert TIMESTAMP_PRECISION == "microsecond"


def test_decimal_policy_is_canonical_normalization():
    assert DECIMAL_POLICY == "canonical_normalization"


def test_binary_encoding_is_base64():
    assert BINARY_ENCODING == "base64"


def test_null_semantics_is_explicit():
    assert NULL_SEMANTICS == "explicit"


def test_hash_algorithm_is_sha256():
    assert HASH_ALGORITHM == "sha-256"


def test_hash_display_length_is_12():
    assert HASH_DISPLAY_LENGTH == 12


def test_hash_internal_length_is_32():
    assert HASH_INTERNAL_LENGTH == 32


def test_reserved_payload_namespaces():
    assert "meta" in RESERVED_PAYLOAD_NAMESPACES
    assert "internal" in RESERVED_PAYLOAD_NAMESPACES
    assert "experimental" in RESERVED_PAYLOAD_NAMESPACES
