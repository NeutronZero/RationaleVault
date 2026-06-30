"""Unit proofs for decision_proposed_v1_to_v2 upcaster correctness."""
from rationalevault.schema.upcaster import decision_proposed_v1_to_v2


class TestDecisionProposedV1ToV2:
    """Verify the upcaster transforms v1 payloads to canonical v2."""

    def test_adds_default_context(self) -> None:
        """v1 payload without context gets context=""."""
        v1 = {"decision_id": "d1", "title": "Use FastAPI"}
        result = decision_proposed_v1_to_v2(v1)
        assert result["context"] == ""
        assert result["decision_id"] == "d1"
        assert result["title"] == "Use FastAPI"

    def test_adds_default_category(self) -> None:
        """v1 payload without category gets category="general"."""
        v1 = {"decision_id": "d1", "title": "Use FastAPI"}
        result = decision_proposed_v1_to_v2(v1)
        assert result["category"] == "general"

    def test_preserves_existing_fields(self) -> None:
        """All existing v1 fields are preserved."""
        v1 = {
            "decision_id": "d1",
            "title": "Use FastAPI",
            "description": "For the API layer",
            "rationale": "Simpler than Flask",
        }
        result = decision_proposed_v1_to_v2(v1)
        assert result["decision_id"] == "d1"
        assert result["title"] == "Use FastAPI"
        assert result["description"] == "For the API layer"
        assert result["rationale"] == "Simpler than Flask"
        assert result["context"] == ""
        assert result["category"] == "general"

    def test_does_not_overwrite_existing_context(self) -> None:
        """If context already exists, it is preserved."""
        v1 = {"decision_id": "d1", "title": "T", "context": "prod context"}
        result = decision_proposed_v1_to_v2(v1)
        assert result["context"] == "prod context"

    def test_does_not_overwrite_existing_category(self) -> None:
        """If category already exists, it is preserved."""
        v1 = {"decision_id": "d1", "title": "T", "category": "architectural"}
        result = decision_proposed_v1_to_v2(v1)
        assert result["category"] == "architectural"

    def test_idempotent(self) -> None:
        """Applying the upcaster twice produces the same result."""
        v1 = {"decision_id": "d1", "title": "T"}
        once = decision_proposed_v1_to_v2(v1)
        twice = decision_proposed_v1_to_v2(once)
        assert once == twice
