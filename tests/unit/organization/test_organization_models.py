"""Unit tests for organization state models."""
from __future__ import annotations

from rationalevault.organization.models import (
    TransferabilityTelemetry,
    KnowledgeLineage,
    SharedKnowledge,
)


def test_telemetry_serialization() -> None:
    telemetry = TransferabilityTelemetry(
        local_only_count=2,
        reusable_count=3,
        organizational_count=4,
    )
    assert telemetry.to_dict()["local_only_count"] == 2


def test_lineage_serialization() -> None:
    lineage = KnowledgeLineage(
        knowledge_id="k-1",
        origin_project="p-1",
        current_projects=["p-2"],
        depth=1,
    )
    assert lineage.to_dict()["depth"] == 1


def test_shared_knowledge_serialization() -> None:
    sk = SharedKnowledge(
        knowledge_id="k-1",
        title="Shared Title",
        knowledge_type="FACT",
        present_in_projects=["p-1", "p-2"],
    )
    assert sk.to_dict()["knowledge_id"] == "k-1"
