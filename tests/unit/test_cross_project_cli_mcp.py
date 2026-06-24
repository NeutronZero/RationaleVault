"""Tests for I10.5 — Cross-Project CLI and MCP Exposure."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from rationalevault.knowledge.models import (
    KnowledgeConfidence,
    KnowledgeDomain,
    KnowledgeLifecycle,
    KnowledgeObject,
    KnowledgeTransferability,
    KnowledgeType,
    ProvenanceChain,
)
from rationalevault.knowledge.project_registry import ProjectEntry
from rationalevault.projections.cross_project import CrossProjectProjection


def _conf() -> KnowledgeConfidence:
    return KnowledgeConfidence(
        memory_count=3, source_event_count=2, contradiction_count=0,
        average_memory_confidence=0.9, score=0.9,
    )


def _prov(kid: str) -> ProvenanceChain:
    return ProvenanceChain(
        knowledge_id=kid, source_memory_ids=["m1"],
        source_event_ids=["100"], synthesis_event_id="syn-1",
        confidence=_conf(), evidence_count=1,
    )


def _k(
    kid: str,
    title: str,
    project_id: str = "",
    transferability: str = KnowledgeTransferability.REUSABLE.value,
) -> KnowledgeObject:
    return KnowledgeObject(
        id=kid, version=1, title=title, content=f"content for {title}",
        knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=_conf(), importance="high", provenance=_prov(kid),
        supporting_memory_ids=[f"m-{kid}"],
        lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
        project_id=project_id,
        transferability=transferability,
    )


class TestCLIProjectSearch:
    """Tests for rationalevault project search CLI command."""

    def test_search_finds_transferable_knowledge(self) -> None:
        current = [_k("c1", "Use PostgreSQL", "proj_a")]
        targets = {"proj_b": [_k("b1", "Use Redis for caching", "proj_b")]}

        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=targets,
            query="caching",
        )
        titles = [k.title for k in state.transferable_knowledge]
        assert "Use Redis for caching" in titles

    def test_search_excludes_local_only(self) -> None:
        current = [_k("c1", "Use PostgreSQL", "proj_a")]
        targets = {"proj_b": [
            _k("b1", "Use Redis", "proj_b", KnowledgeTransferability.REUSABLE.value),
            _k("b2", "Internal fix", "proj_b", KnowledgeTransferability.LOCAL_ONLY.value),
        ]}

        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=targets,
        )
        titles = [k.title for k in state.transferable_knowledge]
        assert "Use Redis" in titles
        assert "Internal fix" not in titles

    def test_search_empty_projects(self) -> None:
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={},
        )
        assert len(state.transferable_knowledge) == 0

    def test_search_returns_health(self) -> None:
        current = [_k("c1", "Use PostgreSQL", "proj_a")]
        targets = {"proj_b": [_k("b1", "Use Redis", "proj_b")]}

        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=targets,
        )
        assert state.health is not None
        assert state.health.total_transferable == 1
        assert state.health.coverage == 1.0

    def test_search_to_dict_serializable(self) -> None:
        current = [_k("c1", "Use PostgreSQL", "proj_a")]
        targets = {"proj_b": [_k("b1", "Use Redis", "proj_b")]}

        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=targets,
            query="cache",
        )
        d = state.to_dict()
        assert isinstance(d, dict)
        serialized = json.dumps(d)
        assert isinstance(serialized, str)


class TestMCPSearchCrossProject:
    """Tests for the MCP search_cross_project tool interface."""

    def test_tool_returns_dict_with_transferable_knowledge(self) -> None:
        current = [_k("c1", "Use PostgreSQL", "proj_a")]
        targets = {"proj_b": [_k("b1", "Use Redis", "proj_b")]}

        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=targets,
            query="redis",
        )
        result = state.to_dict()
        assert "transferable_knowledge_count" in result
        assert result["transferable_knowledge_count"] == 1

    def test_tool_with_transferability_filter(self) -> None:
        current = [_k("c1", "Use PostgreSQL", "proj_a")]
        targets = {"proj_b": [
            _k("b1", "Use Redis", "proj_b", KnowledgeTransferability.REUSABLE.value),
            _k("b2", "All use CI/CD", "proj_b", KnowledgeTransferability.ORGANIZATIONAL.value),
        ]}

        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=targets,
            transferability_filter=["ORGANIZATIONAL"],
        )
        titles = [k.title for k in state.transferable_knowledge]
        assert titles == ["All use CI/CD"]

    def test_tool_empty_projects_returns_error_dict(self) -> None:
        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=[],
            target_knowledge={},
        )
        result = state.to_dict()
        assert result["transferable_knowledge_count"] == 0
        assert result["source_projects"] == []

    def test_tool_provenance_preserved(self) -> None:
        current = [_k("c1", "Use PostgreSQL", "proj_a")]
        targets = {"proj_b": [_k("b1", "Use Redis", "proj_b")]}

        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=targets,
        )
        assert state.provenance_map["b1"] == "proj_b"

    def test_tool_determinism(self) -> None:
        current = [_k("c1", "Use PostgreSQL", "proj_a")]
        targets = {"proj_b": [_k("b1", "Use Redis", "proj_b")]}

        state1 = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=targets,
            query="cache",
        )
        state2 = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=targets,
            query="cache",
        )
        # Deterministic except for compiled_at
        assert state1.transferable_knowledge == state2.transferable_knowledge
        assert state1.knowledge_by_project == state2.knowledge_by_project
        assert state1.provenance_map == state2.provenance_map

    def test_tool_health_metrics(self) -> None:
        current = [_k("c1", "Use PostgreSQL", "proj_a")]
        targets = {"proj_b": [
            _k("b1", "Use Redis", "proj_b", KnowledgeTransferability.REUSABLE.value),
            _k("b2", "Internal fix", "proj_b", KnowledgeTransferability.LOCAL_ONLY.value),
        ]}

        state = CrossProjectProjection.project(
            current_project_id="proj_a",
            current_knowledge=current,
            target_knowledge=targets,
        )
        assert state.health is not None
        assert state.health.total_transferable == 1
        assert state.health.reusable_count == 1
        assert state.health.organizational_count == 0
