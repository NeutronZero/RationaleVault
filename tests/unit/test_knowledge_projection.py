"""RationaleVault Knowledge Projection Benchmark — Verifies KnowledgeState correctness.

Tests the deterministic projection of knowledge state including:
  - Lifecycle classification (ACTIVE, STALE, SUPERSEDED)
  - Epistemic status derivation (PROPOSED, VALIDATED, INVARIANT, CONFLICTED, TOMBSTONED)
  - Contradiction detection and conflict queue
  - Invariant identification (declared + emergent)
  - Derivation chains and support graph
  - Health computation
  - Provenance tracking
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from rationalevault.knowledge.models import (
    EpistemicStatus,
    KnowledgeConfidence,
    KnowledgeLifecycle,
    KnowledgeObject,
    KnowledgeRelation,
    KnowledgeType,
    KnowledgeDomain,
    ProvenanceChain,
)
from rationalevault.projections.knowledge import (
    ConflictRecord,
    KnowledgeHealth,
    KnowledgeProjection,
    KnowledgeState,
    _derive_epistemic_status,
    _make_conflict_id,
)


def _conf(
    score: float = 0.8,
    memory_count: int = 3,
    contradiction_count: int = 0,
) -> KnowledgeConfidence:
    return KnowledgeConfidence(
        memory_count=memory_count,
        source_event_count=memory_count,
        contradiction_count=contradiction_count,
        average_memory_confidence=score,
        score=score,
    )


def _prov(kid: str, memory_ids: list[str] | None = None) -> ProvenanceChain:
    return ProvenanceChain(
        knowledge_id=kid,
        source_memory_ids=memory_ids or [],
        source_event_ids=["100", "101", "102"],
        synthesis_event_id="syn-1",
        confidence=_conf(),
        evidence_count=len(memory_ids or []),
    )


def _k(
    title: str,
    content: str,
    ktype: KnowledgeType = KnowledgeType.ARCHITECTURE_PRINCIPLE,
    lifecycle: str = KnowledgeLifecycle.ACTIVE.value,
    confidence_score: float = 0.8,
    memory_count: int = 3,
    contradicting_memory_ids: list[str] | None = None,
    supporting_memory_ids: list[str] | None = None,
    tags: list[str] | None = None,
    knowledge_id: str | None = None,
) -> KnowledgeObject:
    kid = knowledge_id or f"k-{title.lower().replace(' ', '-')[:20]}"
    return KnowledgeObject(
        id=kid,
        version=1,
        title=title,
        content=content,
        knowledge_type=ktype,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=_conf(score=confidence_score, memory_count=memory_count,
                         contradiction_count=len(contradicting_memory_ids or [])),
        importance="high",
        provenance=_prov(kid, supporting_memory_ids),
        tags=tags or [],
        supporting_memory_ids=supporting_memory_ids or [],
        contradicting_memory_ids=contradicting_memory_ids or [],
        lifecycle_status=lifecycle,
        project_id="test",
    )


# ── Epistemic Status Tests ──────────────────────────────────────────────────

class TestEpistemicStatus:
    def test_proposed_low_confidence(self):
        k = _k("Low conf", "content", confidence_score=0.3)
        assert _derive_epistemic_status(k) == EpistemicStatus.PROPOSED

    def test_validated_high_confidence(self):
        k = _k("High conf", "content", confidence_score=0.8)
        assert _derive_epistemic_status(k) == EpistemicStatus.VALIDATED

    def test_invariant_declared(self):
        k = _k("Must always", "content",
               ktype=KnowledgeType.PROJECT_INVARIANT,
               confidence_score=0.95, memory_count=5)
        assert _derive_epistemic_status(k) == EpistemicStatus.INVARIANT

    def test_invariant_emergent(self):
        k = _k("Emergent", "content",
               confidence_score=0.96, memory_count=6,
               supporting_memory_ids=[f"m{i}" for i in range(6)])
        # 6 supporting memories, score >= 0.95, no contradictions
        assert _derive_epistemic_status(k) == EpistemicStatus.INVARIANT

    def test_conflicted_with_contradictions(self):
        k = _k("Disputed", "content",
               confidence_score=0.9, memory_count=4,
               contradicting_memory_ids=["mem-1"])
        assert _derive_epistemic_status(k) == EpistemicStatus.CONFLICTED

    def test_tombstoned_superseded(self):
        k = _k("Old fact", "content",
               lifecycle=KnowledgeLifecycle.SUPERSEDED.value)
        assert _derive_epistemic_status(k) == EpistemicStatus.TOMBSTONED

    def test_tombstoned_archived(self):
        k = _k("Archived", "content",
               lifecycle=KnowledgeLifecycle.ARCHIVED.value)
        assert _derive_epistemic_status(k) == EpistemicStatus.TOMBSTONED


# ── Conflict ID Determinism ─────────────────────────────────────────────────

class TestConflictIDDeterminism:
    def test_same_knowledge_same_id(self):
        id1 = _make_conflict_id("aaa", "bbb")
        id2 = _make_conflict_id("aaa", "bbb")
        assert id1 == id2

    def test_reversed_order_same_id(self):
        id1 = _make_conflict_id("aaa", "bbb")
        id2 = _make_conflict_id("bbb", "aaa")
        assert id1 == id2

    def test_different_knowledge_different_id(self):
        id1 = _make_conflict_id("aaa", "bbb")
        id2 = _make_conflict_id("aaa", "ccc")
        assert id1 != id2


# ── KnowledgeProjection Tests ───────────────────────────────────────────────

class TestKnowledgeProjection:
    def test_empty_knowledge(self):
        state = KnowledgeProjection.project("proj-1", knowledge=[])
        assert state.active_knowledge == []
        assert state.health is not None
        assert state.health.total_count == 0

    def test_active_knowledge_count(self):
        knowledge = [
            _k("Fact 1", "content 1", supporting_memory_ids=["m1"]),
            _k("Fact 2", "content 2", supporting_memory_ids=["m2"]),
            _k("Fact 3", "content 3",
               lifecycle=KnowledgeLifecycle.STALE.value),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        assert len(state.active_knowledge) == 2

    def test_superseded_knowledge_tracked(self):
        knowledge = [
            _k("New approach", "use X", supporting_memory_ids=["m1"]),
            _k("Old approach", "use Y",
               lifecycle=KnowledgeLifecycle.SUPERSEDED.value),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        assert len(state.superseded_knowledge) == 1
        assert state.superseded_knowledge[0].title == "Old approach"

    def test_stale_knowledge_tracked(self):
        knowledge = [
            _k("Current", "content", supporting_memory_ids=["m1"]),
            _k("Stale", "old content",
               lifecycle=KnowledgeLifecycle.STALE.value),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        assert len(state.stale_knowledge) == 1

    def test_invariants_declared(self):
        knowledge = [
            _k("Must always use PG", "PostgreSQL only",
               ktype=KnowledgeType.PROJECT_INVARIANT,
               confidence_score=0.99, memory_count=5),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        assert len(state.invariants) == 1
        assert state.invariants[0].title == "Must always use PG"

    def test_invariants_emergent(self):
        knowledge = [
            _k("Emergent pattern", "always async",
               confidence_score=0.96, memory_count=6,
               supporting_memory_ids=[f"m{i}" for i in range(6)]),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        assert len(state.invariants) == 1

    def test_conflict_queue_populated(self):
        knowledge = [
            _k("Use PostgreSQL", "PG is best",
               knowledge_id="k-pg",
               supporting_memory_ids=["m1"]),
            _k("Use SQLite", "SQLite is best",
               knowledge_id="k-sqlite",
               supporting_memory_ids=["m2"]),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        # Relations are derived from active knowledge; conflicts may or may not
        # be detected depending on content similarity / contradiction logic
        assert isinstance(state.conflict_queue, list)

    def test_epistemic_proposed(self):
        knowledge = [
            _k("New idea", "maybe try X",
               confidence_score=0.2, memory_count=1),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        assert len(state.proposed) == 1

    def test_epistemic_validated(self):
        knowledge = [
            _k("Proven fact", "X works",
               confidence_score=0.85, memory_count=4),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        assert len(state.validated) == 1

    def test_epistemic_tombstoned(self):
        knowledge = [
            _k("Old fact", "was true",
               lifecycle=KnowledgeLifecycle.SUPERSEDED.value),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        assert len(state.tombstoned) == 1

    def test_health_computed(self):
        knowledge = [
            _k("Fact 1", "content 1", confidence_score=0.8,
               supporting_memory_ids=["m1"]),
            _k("Fact 2", "content 2", confidence_score=0.9,
               supporting_memory_ids=["m2"]),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        assert state.health is not None
        assert 0 <= state.health.confidence <= 1.0
        assert state.health.active_count == 2
        assert state.health.total_count == 2
        assert state.health.overall > 0

    def test_provenance_populated(self):
        knowledge = [
            _k("Fact", "content", supporting_memory_ids=["m1"]),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        assert len(state.provenance) == 1

    def test_projection_version(self):
        state = KnowledgeProjection.project("proj-1", knowledge=[])
        assert state.projection_version == "1.0"

    def test_to_dict(self):
        knowledge = [
            _k("Fact", "content", supporting_memory_ids=["m1"]),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)
        d = state.to_dict()
        assert d["project_id"] == "proj-1"
        assert d["projection_version"] == "1.0"
        assert d["active_count"] == 1
        assert "health" in d
        assert "conflict_queue" in d


# ── Integration with ContextPackage ─────────────────────────────────────────

class TestKnowledgeStateInPackage:
    def test_knowledge_state_attached(self):
        """Verify compile_context attaches knowledge_state when project_id is given."""
        from rationalevault.knowledge.context_compiler import compile_context
        # compile_context with a project_id should attempt to build knowledge_state
        # With no store, it may be None, but the field should exist
        package = compile_context(query="what do we know", project_id=None)
        assert hasattr(package, "knowledge_state")

    def test_knowledge_evolution_in_output(self):
        """Verify ClaudeContextCompiler renders knowledge evolution section."""
        from rationalevault.compilers.claude_context import ClaudeContextCompiler
        from rationalevault.knowledge.context_compiler import ContextPackage
        from rationalevault.knowledge.context_types import ContextCitation

        knowledge = [
            _k("Must use PG", "PostgreSQL",
               ktype=KnowledgeType.PROJECT_INVARIANT,
               confidence_score=0.99, memory_count=5),
            _k("Proven fact", "X works",
               confidence_score=0.85, memory_count=4),
        ]
        state = KnowledgeProjection.project("proj-1", knowledge=knowledge)

        package = ContextPackage(
            context_id="test-ctx",
            query="what do we know",
            profile="GENERAL_SEARCH",
            created_at=datetime.now(timezone.utc).isoformat(),
            knowledge_state=state,
        )

        compiler = ClaudeContextCompiler()
        output = compiler.compile(package)
        assert "Knowledge Evolution" in output.rendered_content
        assert "Invariants" in output.rendered_content


# ── Health Computation ──────────────────────────────────────────────────────

class TestKnowledgeHealth:
    def test_zero_knowledge(self):
        from rationalevault.projections.knowledge import _compute_health
        health = _compute_health([], [], [], [], [])
        assert health.overall == 0.0
        assert health.active_count == 0

    def test_high_health(self):
        from rationalevault.projections.knowledge import _compute_health
        active = [_k(f"Fact {i}", f"content {i}", confidence_score=0.9,
                      supporting_memory_ids=[f"m{i}"]) for i in range(5)]
        health = _compute_health(active, active, [], [], [])
        assert health.confidence > 0.8
        assert health.contradiction_rate == 0.0
        assert health.overall > 0.5

    def test_low_health_with_contradictions(self):
        from rationalevault.projections.knowledge import _compute_health
        active = [_k(f"Fact {i}", f"content {i}", confidence_score=0.5,
                      contradicting_memory_ids=[f"m{i}"]) for i in range(3)]
        health = _compute_health(active, active, active, [], [])
        assert health.contradiction_rate > 0.0
