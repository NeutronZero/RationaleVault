"""Unit tests for organization graph relation types enum parsing."""
from __future__ import annotations

import pytest
from rationalevault.organization.relation_types import OrganizationRelationType


def test_relation_types_parsing() -> None:
    assert OrganizationRelationType.from_str("shared_by") == OrganizationRelationType.SHARED_BY
    assert OrganizationRelationType.from_str("CONFLICTS_WITH") == OrganizationRelationType.CONFLICTS_WITH

    with pytest.raises(ValueError):
        OrganizationRelationType.from_str("invalid")
