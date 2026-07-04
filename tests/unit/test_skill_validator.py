"""
RationaleVault Unit Tests — SkillValidator.
"""
from rationalevault.skill_platform.validator import OutputValidator, ValidationResult


class TestOutputValidator:
    def test_valid_output(self):
        schema = {
            "type": "object",
            "required": ["status", "summary"],
            "properties": {
                "status": {"type": "string"},
                "summary": {"type": "string"},
            },
        }
        output = {"status": "completed", "summary": "all good"}
        result = OutputValidator.validate(output, schema)
        assert result.valid is True
        assert result.errors == []

    def test_missing_required_field(self):
        schema = {
            "type": "object",
            "required": ["status", "summary"],
            "properties": {
                "status": {"type": "string"},
                "summary": {"type": "string"},
            },
        }
        output = {"status": "completed"}
        result = OutputValidator.validate(output, schema)
        assert result.valid is False
        assert len(result.errors) == 1
        assert "Missing required field: summary" in result.errors[0]

    def test_wrong_type(self):
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
        }
        output = {"count": "not a number"}
        result = OutputValidator.validate(output, schema)
        assert result.valid is False
        assert "count" in result.errors[0]

    def test_unexpected_field_warning(self):
        schema = {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
            },
        }
        output = {"status": "ok", "extra_field": "value"}
        result = OutputValidator.validate(output, schema)
        assert result.valid is True
        assert len(result.warnings) == 1
        assert "extra_field" in result.warnings[0]

    def test_empty_schema_passes(self):
        result = OutputValidator.validate({"anything": "goes"}, {})
        assert result.valid is True

    def test_to_dict(self):
        r = ValidationResult(valid=True, errors=[], warnings=[])
        d = r.to_dict()
        assert d["valid"] is True
        assert d["errors"] == []

    def test_evaluation_version(self):
        r = OutputValidator.validate({}, {})
        assert r.evaluation_version == "1.0"
