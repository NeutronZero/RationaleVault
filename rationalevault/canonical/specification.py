"""RVCJ v1 Specification — Normative constants, no logic."""

RVCJ_VERSION = 1
EVENT_SCHEMA_VERSION = 1

KEY_ORDERING = "lexicographic"
UNICODE_NORMALIZATION = "NFC"
TIMESTAMP_FORMAT = "RFC3339-UTC"
TIMESTAMP_PRECISION = "microsecond"
DECIMAL_POLICY = "canonical_normalization"
BINARY_ENCODING = "base64"
NULL_SEMANTICS = "explicit"

HASH_ALGORITHM = "sha-256"
HASH_DISPLAY_LENGTH = 12
HASH_INTERNAL_LENGTH = 32  # bytes

RESERVED_PAYLOAD_NAMESPACES = ["meta", "internal", "experimental"]
