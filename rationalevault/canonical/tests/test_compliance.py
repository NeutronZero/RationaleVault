from rationalevault.canonical.compliance.validator import ComplianceValidator


def test_compliance_vectors_exist():
    vectors = ComplianceValidator.load_vectors()
    assert len(vectors) > 0


def test_compliance_key_ordering():
    result = ComplianceValidator.validate_vector("key_ordering")
    assert result.passed, result.message


def test_compliance_unicode_normalization():
    result = ComplianceValidator.validate_vector("unicode_normalization")
    assert result.passed, result.message


def test_compliance_decimal_normalization():
    result = ComplianceValidator.validate_vector("decimal_normalization")
    assert result.passed, result.message


def test_compliance_timestamp_format():
    result = ComplianceValidator.validate_vector("timestamp_format")
    assert result.passed, result.message


def test_compliance_null_semantics():
    result = ComplianceValidator.validate_vector("null_semantics")
    assert result.passed, result.message


def test_compliance_binary_encoding():
    result = ComplianceValidator.validate_vector("binary_encoding")
    assert result.passed, result.message


def test_compliance_array_ordering():
    result = ComplianceValidator.validate_vector("array_ordering")
    assert result.passed, result.message


def test_compliance_deep_nesting():
    result = ComplianceValidator.validate_vector("deep_nesting")
    assert result.passed, result.message


def test_compliance_empty_payload():
    result = ComplianceValidator.validate_vector("empty_payload")
    assert result.passed, result.message


def test_compliance_large_integers():
    result = ComplianceValidator.validate_vector("large_integers")
    assert result.passed, result.message


def test_compliance_unicode_combining():
    result = ComplianceValidator.validate_vector("unicode_combining")
    assert result.passed, result.message


def test_compliance_mixed_normalization():
    result = ComplianceValidator.validate_vector("mixed_normalization")
    assert result.passed, result.message