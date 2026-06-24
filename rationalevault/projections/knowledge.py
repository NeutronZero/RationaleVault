"""RationaleVault Knowledge Projection — Deterministic knowledge state projection.

KnowledgeState = KnowledgeProjection.project(knowledge)

Produces a compiled snapshot of all knowledge in a project, classified by:
  - Lifecycle: ACTIVE / STALE / SUPERSEDED / ARCHIVED (freshness)
  - Epistemic: PROPOSED / VALIDATED / INVARIANT / CONFLICTED / TOMBSTONED (confidence)

Relations are derived (not persisted):
  - CONTRADICTS → conflict_queue
  - DERIVED_FROM → derivation_chains
  - SUPPORTS → support_graph

Design constraints:
  - No I/O during projection (store read happens once at entry)
  - Deterministic: same knowledge → identical KnowledgeState
  - Replayable: relations recomputed from knowledge on every projection
  - Provenance: every derived field traceable to source knowledge
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from rationalevault.knowledge.models import (
    EpistemicStatus,
    KnowledgeConfidence,
    KnowledgeLifecycle,
    KnowledgeObject,
    KnowledgeRelation,
    KnowledgeType,
)
from rationalevault.knowledge.relation_types import RelationType
from rationalevault.knowledge.relations import detect_relations, build_derivation_chain


# ── KnowledgeHealth ──────────────────────────────────────────────────────────

@dataclass
class KnowledgeHealth:
    """Observable system health metrics for knowledge quality.

    Single metric surface for CLI, MCP, Evaluation, and Compilers.
    """
    confidence: float           # avg confidence across active knowledge
    contradiction_rate: float   # contradicted / total active
    invariant_ratio: float      # invariants / total active
    stale_ratio: float          # stale / total (lifecycle dimension)
    active_count: int
    total_count: int
    overall: float              # weighted composite score

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": round(self.confidence, 4),
            "contradiction_rate": round(self.contradiction_rate, 4),
            "invariant_ratio": round(self.invariant_ratio, 4),
            "stale_ratio": round(self.stale_ratio, 4),
            "active_count": self.active_count,
            "total_count": self.total_count,
            "overall": round(self.overall, 4),
        }


def _compute_health(
    active: list[KnowledgeObject],
    all_knowledge: list[KnowledgeObject],
    conflicted: list[KnowledgeObject],
    invariants: list[KnowledgeObject],
    stale: list[KnowledgeObject],
) -> KnowledgeHealth:
    """Compute knowledge health metrics from classified knowledge."""
    total = len(all_knowledge)
    active_count = len(active)

    if active_count == 0:
        return KnowledgeHealth(
            confidence=0.0, contradiction_rate=0.0, invariant_ratio=0.0,
            stale_ratio=0.0, active_count=0, total_count=total, overall=0.0,
        )

    avg_confidence = sum(k.confidence.score for k in active) / active_count
    contradiction_rate = len(conflicted) / active_count
    invariant_ratio = len(invariants) / active_count
    stale_ratio = len(stale) / total if total > 0 else 0.0

    # Weighted composite: high confidence + low contradictions + some invariants
    overall = (
        avg_confidence * 0.4
        + (1.0 - contradiction_rate) * 0.3
        + min(invariant_ratio, 0.3) * 0.2
        + (1.0 - stale_ratio) * 0.1
    )

    return KnowledgeHealth(
        confidence=avg_confidence,
        contradiction_rate=contradiction_rate,
        invariant_ratio=invariant_ratio,
        stale_ratio=stale_ratio,
        active_count=active_count,
        total_count=total,
        overall=overall,
    )


# ── ConflictRecord ───────────────────────────────────────────────────────────

@dataclass
class ConflictRecord:
    """A contradiction requiring resolution.

    Surfaces "things requiring resolution" not merely "things that disagree."
    Deterministic conflict_id: same knowledge → same conflict ID.
    """
    conflict_id: str
    knowledge_a_id: str
    knowledge_b_id: str
    knowledge_a_title: str
    knowledge_b_title: str
    confidence: float
    raised_at: str
    resolution_status: str = "unresolved"  # unresolved | superseded | acknowledged

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "knowledge_a_id": self.knowledge_a_id,
            "knowledge_b_id": self.knowledge_b_id,
            "knowledge_a_title": self.knowledge_a_title,
            "knowledge_b_title": self.knowledge_b_title,
            "confidence": self.confidence,
            "raised_at": self.raised_at,
            "resolution_status": self.resolution_status,
        }


def _make_conflict_id(a_id: str, b_id: str) -> str:
    """Deterministic conflict ID from two knowledge IDs."""
    pair = ":".join(sorted([a_id, b_id]))
    return hashlib.sha256(pair.encode("utf-8")).hexdigest()[:16]


# ── Epistemic Classification ─────────────────────────────────────────────────

def _derive_epistemic_status(k: KnowledgeObject) -> EpistemicStatus:
    """Derive epistemic status from knowledge properties.

    Rules (evaluated in priority order):
      1. TOMBSTONED: lifecycle is SUPERSEDED or ARCHIVED
      2. CONFLICTED: has contradictions
      3. INVARIANT: declared (PROJECT_INVARIANT) or emergent (high confidence + strong evidence)
      4. VALIDATED: high confidence, no contradictions
      5. PROPOSED: everything else
    """
    if k.lifecycle_status in (KnowledgeLifecycle.SUPERSEDED.value, KnowledgeLifecycle.ARCHIVED.value):
        return EpistemicStatus.TOMBSTONED

    contradiction_count = len(k.contradicting_memory_ids)

    if contradiction_count > 0:
        return EpistemicStatus.CONFLICTED

    # Declared invariant
    if k.knowledge_type == KnowledgeType.PROJECT_INVARIANT:
        return EpistemicStatus.INVARIANT

    # Emergent invariant: high confidence, strong evidence, no contradictions
    if (k.confidence.score >= 0.95
            and len(k.supporting_memory_ids) >= 5
            and contradiction_count == 0):
        return EpistemicStatus.INVARIANT

    if k.confidence.score >= 0.7 and contradiction_count == 0:
        return EpistemicStatus.VALIDATED

    return EpistemicStatus.PROPOSED


def _identify_invariants(knowledge: list[KnowledgeObject]) -> list[KnowledgeObject]:
    """Identify invariants: declared (PROJECT_INVARIANT) + emergent (high confidence)."""
    invariants = []
    for k in knowledge:
        if k.lifecycle_status != KnowledgeLifecycle.ACTIVE.value:
            continue
        if k.knowledge_type == KnowledgeType.PROJECT_INVARIANT:
            invariants.append(k)
        elif (k.confidence.score >= 0.95
              and len(k.supporting_memory_ids) >= 5
              and len(k.contradicting_memory_ids) == 0):
            invariants.append(k)
    return invariants


# ── KnowledgeState ───────────────────────────────────────────────────────────

@dataclass
class KnowledgeState:
    """Compiled knowledge state of a project.

    Two orthogonal dimensions:
      Lifecycle: ACTIVE / STALE / SUPERSEDED / ARCHIVED (freshness)
      Epistemic: PROPOSED / VALIDATED / INVARIANT / CONFLICTED / TOMBSTONED (confidence)

    Produced by KnowledgeProjection.project().
    Deterministic: same knowledge → identical state.
    """
    project_id: str
    compiled_at: str
    projection_version: str = "1.0"

    # Lifecycle buckets
    active_knowledge: list[KnowledgeObject] = field(default_factory=list)
    stale_knowledge: list[KnowledgeObject] = field(default_factory=list)
    superseded_knowledge: list[KnowledgeObject] = field(default_factory=list)

    # Epistemic buckets (derived)
    proposed: list[KnowledgeObject] = field(default_factory=list)
    validated: list[KnowledgeObject] = field(default_factory=list)
    invariants: list[KnowledgeObject] = field(default_factory=list)
    conflicted: list[KnowledgeObject] = field(default_factory=list)
    tombstoned: list[KnowledgeObject] = field(default_factory=list)

    # Contradiction queue (actionable)
    conflict_queue: list[ConflictRecord] = field(default_factory=list)
    unresolved_count: int = 0

    # Derived adjacency (lightweight — no graph traversal)
    derivation_chains: dict[str, list[str]] = field(default_factory=dict)
    support_graph: dict[str, list[str]] = field(default_factory=dict)

    # Health
    health: Optional[KnowledgeHealth] = None

    # Provenance
    provenance: dict[str, list[int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "compiled_at": self.compiled_at,
            "projection_version": self.projection_version,
            "active_count": len(self.active_knowledge),
            "stale_count": len(self.stale_knowledge),
            "superseded_count": len(self.superseded_knowledge),
            "proposed_count": len(self.proposed),
            "validated_count": len(self.validated),
            "invariant_count": len(self.invariants),
            "conflicted_count": len(self.conflicted),
            "tombstoned_count": len(self.tombstoned),
            "unresolved_count": self.unresolved_count,
            "conflict_queue": [c.to_dict() for c in self.conflict_queue],
            "health": self.health.to_dict() if self.health else None,
            "provenance": self.provenance,
        }


# ── KnowledgeProjection ──────────────────────────────────────────────────────

class KnowledgeProjection:
    """Derives KnowledgeState from knowledge objects.

    Relations are derived (not persisted). Same knowledge → same relations.
    """

    @staticmethod
    def project(
        project_id: str,
        knowledge: Optional[list[KnowledgeObject]] = None,
        reference_time: Optional[datetime] = None,
    ) -> KnowledgeState:
        """Project knowledge state from knowledge objects.

        Args:
            project_id: Project UUID string.
            knowledge: Optional pre-loaded knowledge objects.
                      If None, loads from configured provider.
            reference_time: Optional reference time to run projection deterministically.

        Returns:
            KnowledgeState with all classifications, relations, and health.
        """
        from rationalevault.organization.utils import resolve_compiled_at
        now = resolve_compiled_at(reference_time)

        # 1. Load knowledge if not provided
        if knowledge is None:
            from rationalevault.knowledge.factory import get_knowledge_provider
            knowledge = get_knowledge_provider().get_all_knowledge()

        # 2. Classify by lifecycle
        active = [k for k in knowledge if k.lifecycle_status == KnowledgeLifecycle.ACTIVE.value]
        stale = [k for k in knowledge if k.lifecycle_status == KnowledgeLifecycle.STALE.value]
        superseded = [k for k in knowledge if k.lifecycle_status == KnowledgeLifecycle.SUPERSEDED.value]
        archived = [k for k in knowledge if k.lifecycle_status == KnowledgeLifecycle.ARCHIVED.value]

        # 3. Derive epistemic status for each object
        proposed = []
        validated = []
        invariants_list = []
        conflicted = []
        tombstoned = []

        for k in knowledge:
            status = _derive_epistemic_status(k)
            if status == EpistemicStatus.PROPOSED:
                proposed.append(k)
            elif status == EpistemicStatus.VALIDATED:
                validated.append(k)
            elif status == EpistemicStatus.INVARIANT:
                invariants_list.append(k)
            elif status == EpistemicStatus.CONFLICTED:
                conflicted.append(k)
            elif status == EpistemicStatus.TOMBSTONED:
                tombstoned.append(k)

        # 4. Identify invariants (declared + emergent)
        invariants_from_evidence = _identify_invariants(active)
        # Merge: declared invariants + emergent, deduplicate by ID
        seen_ids = set()
        all_invariants = []
        for inv in invariants_list + invariants_from_evidence:
            if inv.id not in seen_ids:
                all_invariants.append(inv)
                seen_ids.add(inv.id)

        # 5. Detect relations from ACTIVE knowledge only
        relations = detect_relations(active)
        derivation_chains = build_derivation_chain(active)

        # 6. Build conflict queue from CONTRADICTS relations
        active_by_id = {k.id: k for k in active}
        conflict_queue = []
        for rel in relations:
            if rel.relation_type == RelationType.CONTRADICTS:
                # Find the knowledge objects for titles
                a_obj = active_by_id.get(rel.source_id)
                b_obj = active_by_id.get(rel.target_id)
                if a_obj and b_obj:
                    conflict_queue.append(ConflictRecord(
                         conflict_id=_make_conflict_id(rel.source_id, rel.target_id),
                         knowledge_a_id=rel.source_id,
                         knowledge_b_id=rel.target_id,
                         knowledge_a_title=a_obj.title,
                         knowledge_b_title=b_obj.title,
                         confidence=rel.confidence,
                         raised_at=now,
                     ))

        # 7. Build support graph from SUPPORTS relations
        support_graph: dict[str, list[str]] = {}
        for rel in relations:
            if rel.relation_type == RelationType.SUPPORTS:
                support_graph.setdefault(rel.source_id, []).append(rel.target_id)

        # 8. Compute health
        health = _compute_health(active, knowledge, conflicted, all_invariants, stale)

        # 9. Build provenance
        provenance: dict[str, list[int]] = {}
        for k in active:
            if k.provenance and k.provenance.source_event_ids:
                provenance[k.id] = [
                    int(eid) for eid in k.provenance.source_event_ids
                    if eid.isdigit()
                ]

        return KnowledgeState(
            project_id=project_id,
            compiled_at=now,
            active_knowledge=active,
            stale_knowledge=stale,
            superseded_knowledge=superseded + archived,
            proposed=proposed,
            validated=validated,
            invariants=all_invariants,
            conflicted=conflicted,
            tombstoned=tombstoned,
            conflict_queue=conflict_queue,
            unresolved_count=len(conflict_queue),
            derivation_chains=derivation_chains,
            support_graph=support_graph,
            health=health,
            provenance=provenance,
        )
