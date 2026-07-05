"""RationaleVault Context Compiler — Unified retrieval blending events, memories, and knowledge.

compile_context(query, profile?) → ContextPackage

This is the Sprint I5 entry point. It blends three retrieval pipelines
into one coherent context package using profile-based slot allocation.

Pipeline:
    1. Analyze query → determine profile + keywords
    2. Retrieve memory citations (existing pipeline)
    3. Retrieve knowledge citations (new pipeline)
    4. Retrieve relevant recent events (new pipeline)
    5. Blend all three using profile-based slot allocation
    6. Assemble ContextPackage

Design constraints:
    - No LLM dependency
    - No vector database dependency
    - All context traceable to source events
    - Deterministic: same input → same output
    - Follows existing patterns (keyword matching, profile weights)
"""
from __future__ import annotations

from enum import Enum
import hashlib
import time
import uuid
import warnings
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from rationalevault.knowledge.context_types import (
    ContextCitation,
    EventContext,
)
from rationalevault.knowledge.knowledge_retrieval import (
    retrieve_ranked_knowledge_citations,
)
from rationalevault.memory.query_analyzer import QueryIntent, RetrievalProfile, analyze_query
from rationalevault.memory.retrieval import retrieve_ranked_citations

class ContextMode(str, Enum):
    """
    Controls HOW context is assembled — independent of WHAT information is needed.

    STANDARD:     Normal profile-driven retrieval blend.
    CONTINUATION: Optimized for agent resumption. Elevates recent events.
                  Populates ContextPackage.continuation_state.
    """
    STANDARD     = "standard"
    CONTINUATION = "continuation"

_CONTINUATION_SOURCE_WEIGHTS: dict[str, float] = {
    "event": 0.40, "memory": 0.35, "knowledge": 0.25
}



# ── Profile Source Weight Matrix ────────────────────────────────────────────

PROFILE_SOURCE_WEIGHTS: dict[RetrievalProfile, dict[str, float]] = {
    RetrievalProfile.KNOWLEDGE_REVIEW:     {"event": 0.10, "memory": 0.20, "knowledge": 0.70},
    RetrievalProfile.PROJECT_OVERVIEW:     {"event": 0.30, "memory": 0.30, "knowledge": 0.40},
    RetrievalProfile.CONTEXT_CONSTRUCTION: {"event": 0.25, "memory": 0.40, "knowledge": 0.35},
    RetrievalProfile.FAILURE_ANALYSIS:     {"event": 0.30, "memory": 0.50, "knowledge": 0.20},
    RetrievalProfile.ARCHITECTURE_REVIEW:  {"event": 0.20, "memory": 0.35, "knowledge": 0.45},
    RetrievalProfile.DECISION_LOOKUP:      {"event": 0.25, "memory": 0.50, "knowledge": 0.25},
    RetrievalProfile.LESSON_DISCOVERY:     {"event": 0.15, "memory": 0.45, "knowledge": 0.40},
    RetrievalProfile.WORKFLOW_RETRIEVAL:   {"event": 0.20, "memory": 0.50, "knowledge": 0.30},
    RetrievalProfile.GENERAL_SEARCH:       {"event": 0.20, "memory": 0.45, "knowledge": 0.35},
}


# ── Context Package ─────────────────────────────────────────────────────────

@dataclass
class ContextPackage:
    """Unified retrieval result blending events, memories, and knowledge.

    This is the top-level output of compile_context(). It contains:
    - Citations: Ranked context items from all three sources
    - Inclusion reasons: Why the package looks the way it does
    - Source counts: How many items from each source
    - Timing: Execution timing breakdown

    Design invariants:
    - Every citation is traceable to at least one source event
    - No LLM dependency
    - Deterministic: same input always produces the same package
    - Agent-agnostic: agent compilers consume this, not emit it
    """
    context_id: str
    query: str
    profile: str
    created_at: str

    citations: list[ContextCitation] = field(default_factory=list)
    inclusion_reasons: list[str] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)
    timing: dict[str, float] = field(default_factory=dict)
    mode: str = "standard"
    continuation_state: Optional[Any] = None
    knowledge_state: Optional[Any] = None
    graph_state: Optional[Any] = None
    cross_project_state: Optional[Any] = None
    organization_state: Optional[Any] = None
    organization_continuation_state: Optional[Any] = None
    retrieval_plan: Optional[Any] = None
    recommendations: Optional[Any] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "query": self.query,
            "profile": self.profile,
            "created_at": self.created_at,
            "citations": [c.to_dict() for c in self.citations],
            "inclusion_reasons": self.inclusion_reasons,
            "source_counts": self.source_counts,
            "timing": self.timing,
            "mode": self.mode,
            "continuation_state": self.continuation_state.to_dict() if self.continuation_state else None,
            "graph_state": self.graph_state.to_dict() if self.graph_state else None,
            "cross_project_state": self.cross_project_state.to_dict() if self.cross_project_state else None,
            "organization_state": self.organization_state.to_dict() if self.organization_state else None,
            "organization_continuation_state": self.organization_continuation_state.to_dict() if self.organization_continuation_state else None,
            "retrieval_plan": self.retrieval_plan.to_dict() if self.retrieval_plan else None,
            "recommendations": self.recommendations.to_dict() if self.recommendations else None,
        }


# ── Slot Allocation ─────────────────────────────────────────────────────────

def _get_slot_allocation(
    profile: RetrievalProfile,
    total_limit: int,
    mode: ContextMode = ContextMode.STANDARD,
) -> dict[str, int]:
    """Convert profile weights to integer slot counts."""
    if mode == ContextMode.CONTINUATION:
        weights = _CONTINUATION_SOURCE_WEIGHTS
    else:
        weights = PROFILE_SOURCE_WEIGHTS.get(
            profile, PROFILE_SOURCE_WEIGHTS[RetrievalProfile.GENERAL_SEARCH]
        )
    slots = {}
    for source, ratio in weights.items():

        slots[source] = max(0, round(total_limit * ratio))

    total = sum(slots.values())
    if total > total_limit:
        excess = total - total_limit
        largest = max(slots, key=slots.get)
        slots[largest] -= excess

    return slots


# ── Event Retrieval ─────────────────────────────────────────────────────────

def _summarize_event_payload(event_type: str, payload: dict[str, Any]) -> str:
    """Produce a one-line human-readable summary from an event payload."""
    summaries = {
        "PROJECT_CREATED": lambda p: f"Project created: {p.get('name', 'unnamed')}",
        "PROJECT_GOAL_SET": lambda p: f"Goal set: {p.get('goal', 'unspecified')}",
        "PROJECT_FOCUS_CHANGED": lambda p: f"Focus changed to: {p.get('focus', 'unspecified')}",
        "TASK_CREATED": lambda p: f"Task created: {p.get('title', 'untitled')}",
        "TASK_COMPLETED": lambda p: f"Task completed: {p.get('title', 'untitled')}",
        "DECISION_ACCEPTED": lambda p: f"Decision accepted: {p.get('title', 'untitled')}",
        "DECISION_SUPERSEDED": lambda p: f"Decision superseded: {p.get('title', 'untitled')}",
        "OPEN_QUESTION_RAISED": lambda p: f"Question raised: {p.get('title', 'untitled')}",
        "OPEN_QUESTION_RESOLVED": lambda p: f"Question resolved: {p.get('title', 'untitled')}",
        "KNOWLEDGE_SYNTHESIZED": lambda p: f"Knowledge synthesized: {p.get('title', 'untitled')}",
        "KNOWLEDGE_CONTRADICTION": lambda p: "Knowledge contradiction detected",
        "MEMORY_RECORDED": lambda p: f"Memory recorded: {p.get('title', 'untitled')}",
        "TASK_PROGRESS_NOTED":       lambda p: f"Progress on {p.get('task_id','?')}: {p.get('note','')}",
        "CONTEXT_SNAPSHOT_RECORDED": lambda p: f"Snapshot: {p.get('summary','')} | Next: {p.get('next_action','')}",
    }
    formatter = summaries.get(event_type)
    if formatter:
        return formatter(payload)
    return f"{event_type}: {payload.get('title', str(payload)[:80])}"


def _retrieve_relevant_events(
    project_id: uuid.UUID,
    query: str,
    keywords: list[str],
    limit: int = 20,
) -> list[EventContext]:
    """Retrieve recent events relevant to the query keywords."""
    try:
        from rationalevault.db.event_store import EventStore
        store = EventStore()
        events = store.get_project_stream(project_id)
    except Exception:
        return []

    if not events:
        return []

    scored: list[tuple[Any, int]] = []
    for ev in events:
        match_count = 0
        payload_str = str(ev.payload).lower()
        for kw in keywords:
            if kw in payload_str or kw in ev.event_type.value.lower():
                match_count += 1
        scored.append((ev, match_count))

    scored.sort(key=lambda x: (x[1], x[0].event_sequence), reverse=True)

    result: list[EventContext] = []
    for ev, _ in scored[:limit]:
        summary = _summarize_event_payload(ev.event_type.value, ev.payload)
        result.append(EventContext(
            event_id=str(ev.id),
            event_type=ev.event_type.value,
            stream_id=ev.stream_id,
            recorded_at=ev.recorded_at.isoformat() if ev.recorded_at else "",
            actor=ev.metadata.actor,
            source=ev.metadata.source,
            summary=summary,
        ))

    return result


# ── Citation Blending ───────────────────────────────────────────────────────

def _memory_to_context_citation(mc: Any, record_map: dict[str, Any] | None = None) -> ContextCitation:
    """Convert a MemoryCitation to a unified ContextCitation."""
    title = mc.memory_id[:12]
    content = ""
    try:
        if record_map and mc.memory_id in record_map:
            rec = record_map[mc.memory_id]
            title = rec.title
            content = rec.content
        elif record_map is None:
            from rationalevault.memory.factory import get_memory_provider
            provider = get_memory_provider()
            records = provider.get_by_ids([mc.memory_id])
            if records:
                title = records[0].title
                content = records[0].content
    except Exception:
        pass

    return ContextCitation(
        source_type="memory",
        source_id=mc.memory_id,
        title=title,
        content=content,
        relevance_score=mc.score.total,
        confidence=getattr(mc, "confidence", 1.0),
        reasons=mc.reasons,
        source_event_ids=mc.source_event_ids,
    )


def _knowledge_to_context_citation(kc: Any, knowledge_map: dict[str, Any] | None = None) -> ContextCitation:
    """Convert a KnowledgeCitation to a unified ContextCitation."""
    title = kc.knowledge_id[:12]
    content = ""
    try:
        if knowledge_map and kc.knowledge_id in knowledge_map:
            k_obj = knowledge_map[kc.knowledge_id]
            title = k_obj.title
            content = k_obj.content
        elif knowledge_map is None:
            from rationalevault.knowledge.factory import get_knowledge_provider
            provider = get_knowledge_provider()
            k_obj = provider.get_knowledge_by_id(kc.knowledge_id)
            if k_obj:
                title = k_obj.title
                content = k_obj.content
    except Exception:
        pass

    return ContextCitation(
        source_type="knowledge",
        source_id=kc.knowledge_id,
        title=title,
        content=content,
        relevance_score=kc.score.total,
        confidence=kc.score.confidence,
        reasons=kc.reasons,
        source_event_ids=kc.source_event_ids,
    )


def _event_to_context_citation(ec: EventContext) -> ContextCitation:
    """Convert an EventContext to a unified ContextCitation."""
    return ContextCitation(
        source_type="event",
        source_id=ec.event_id,
        title=ec.event_type,
        content=ec.summary,
        relevance_score=0.5,
        confidence=1.0,
        reasons=["recent_event"],
        source_event_ids=[ec.event_id],
    )


def _blend_citations(
    memory_citations: list[Any],
    knowledge_citations: list[Any],
    event_contexts: list[EventContext],
    profile: RetrievalProfile,
    total_limit: int,
    mode: ContextMode = ContextMode.STANDARD,
) -> list[ContextCitation]:
    """Blend all sources into a single ranked list using profile-based slot allocation."""
    slots = _get_slot_allocation(profile, total_limit, mode)

    citations: list[ContextCitation] = []

    # Batch memory lookups
    mem_ids = [mc.memory_id for mc in memory_citations[: slots["memory"]]]
    mem_map: dict[str, Any] = {}
    if mem_ids:
        try:
            from rationalevault.memory.factory import get_memory_provider
            mem_records = get_memory_provider().get_by_ids(mem_ids)
            mem_map = {r.id: r for r in mem_records}
        except Exception:
            pass

    for mc in memory_citations[: slots["memory"]]:
        citations.append(_memory_to_context_citation(mc, record_map=mem_map))

    # Batch knowledge lookups
    kn_ids = [kc.knowledge_id for kc in knowledge_citations[: slots["knowledge"]]]
    kn_map: dict[str, Any] = {}
    if kn_ids:
        try:
            from rationalevault.knowledge.factory import get_knowledge_provider
            kn_objects = get_knowledge_provider().get_knowledge_by_ids(kn_ids)
            kn_map = {k.id: k for k in kn_objects}
        except Exception:
            pass

    for kc in knowledge_citations[: slots["knowledge"]]:
        citations.append(_knowledge_to_context_citation(kc, knowledge_map=kn_map))

    for ec in event_contexts[: slots["event"]]:
        citations.append(_event_to_context_citation(ec))

    citations.sort(key=lambda c: c.relevance_score, reverse=True)

    return citations[:total_limit]


# ── Inclusion Reasons ───────────────────────────────────────────────────────

def _build_inclusion_reasons(
    profile: RetrievalProfile,
    source_counts: dict[str, int],
) -> list[str]:
    """Build package-level inclusion reasons."""
    reasons = [f"Profile {profile.value} selected for query"]
    for source, count in source_counts.items():
        if count > 0:
            reasons.append(f"Retrieved {count} {source} items")
    return reasons


# ── Main Entry Point ────────────────────────────────────────────────────────

def compile_context(
    query: str,
    project_id: uuid.UUID | None = None,
    profile: RetrievalProfile | None = None,
    mode: ContextMode = ContextMode.STANDARD,
    memory_limit: int = 10,
    knowledge_limit: int = 10,
    event_limit: int = 20,
    total_slices: int = 30,
    plan: Optional[Any] = None,
) -> ContextPackage:
    """Compile a unified context package from events, memories, and knowledge.

    Args:
        query: The user's query string.
        project_id: Optional project UUID for event retrieval.
                     If None, event retrieval is skipped.
        profile: Optional profile override. If None, auto-detected from query.
        mode: The context compilation mode (STANDARD or CONTINUATION).
        memory_limit: Max memory citations to retrieve.
        knowledge_limit: Max knowledge citations to retrieve.
        event_limit: Max recent events to include.
        total_slices: Max total citations in the blended output.
        plan: Optional RetrievalPlan from orchestrator. When provided,
              context_weights from the plan override profile weights.
              Backward-compatible: legacy callers unaffected.

    Returns:
        ContextPackage with blended, ranked context from all three sources.
    """
    t_start = time.perf_counter()

    continuation_state = None
    knowledge_state = None
    graph_state = None
    cross_project_state = None
    organization_state = None
    if mode == ContextMode.CONTINUATION:
        event_limit = max(event_limit, 30)
        if project_id is not None:
            from rationalevault.projections.continuation import ContinuationProjection
            continuation_state = ContinuationProjection.project(project_id)

    # Build knowledge projection when project_id is available
    if project_id is not None:
        try:
            from rationalevault.projections.knowledge import KnowledgeProjection
            knowledge_state = KnowledgeProjection.project(str(project_id))
        except Exception as exc:
            warnings.warn(
                f"Knowledge projection failed: {exc}\n"
                f"{traceback.format_exc()}"
            )
            knowledge_state = None

    # Build graph projection lazily — only when it will be used
    if (
        knowledge_state
        and knowledge_state.active_knowledge
        and mode == ContextMode.CONTINUATION
    ):
        try:
            from rationalevault.projections.graph import GraphProjection
            graph_state = GraphProjection.project(knowledge_state)
        except Exception as exc:
            warnings.warn(
                f"Graph projection failed: {exc}\n"
                f"{traceback.format_exc()}"
            )
            graph_state = None

    # Build cross-project state when knowledge_state is available
    target_knowledge: dict[str, list[Any]] = {}
    if knowledge_state and project_id is not None:
        try:
            from rationalevault.knowledge.project_registry import ProjectRegistry
            from rationalevault.knowledge.factory import get_knowledge_provider
            from rationalevault.projections.cross_project import CrossProjectProjection

            registry = ProjectRegistry.load()
            provider = get_knowledge_provider()

            # Load knowledge from registered projects, excluding current project
            for entry in registry.list_projects():
                if entry.id != str(project_id):
                    try:
                        target_knowledge[entry.id] = provider.get_all_knowledge(project_id=entry.id)
                    except Exception as e:
                        warnings.warn(
                            f"Failed to fetch knowledge for project {entry.id}: {e}\n"
                            f"{traceback.format_exc()}"
                        )

            cross_project_state = CrossProjectProjection.project(
                current_project_id=str(project_id),
                current_knowledge=knowledge_state.active_knowledge,
                target_knowledge=target_knowledge,
                query=query,
            )
        except Exception as exc:
            warnings.warn(
                f"Cross-project projection failed: {exc}\n"
                f"{traceback.format_exc()}"
            )
            cross_project_state = None

    # Build organization state when cross_project_state is available
    if cross_project_state is not None:
        try:
            from rationalevault.organization.projection import OrganizationProjection
            from rationalevault.knowledge.project_registry import ProjectRegistry

            registry = ProjectRegistry.load()
            all_knowledge_by_project: dict[str, list[Any]] = {}
            if knowledge_state:
                all_knowledge_by_project[str(project_id)] = list(knowledge_state.active_knowledge)
            
            # Populate other projects' knowledge in all_knowledge_by_project
            for pid, klist in target_knowledge.items():
                all_knowledge_by_project[pid] = klist

            organization_state = OrganizationProjection.project(
                registry=registry,
                cross_project_states={str(project_id): cross_project_state},
                knowledge_by_project=all_knowledge_by_project,
            )
        except Exception as exc:
            warnings.warn(
                f"Organization projection failed: {exc}\n"
                f"{traceback.format_exc()}"
            )
            organization_state = None

    # Build organization continuation when org state is available in continuation mode
    organization_continuation_state = None
    if organization_state is not None and mode == ContextMode.CONTINUATION:
        try:
            from rationalevault.organization.activity import OrganizationActivityProjection
            from rationalevault.organization.continuation import (
                OrganizationContinuationProjection,
            )
            from rationalevault.organization.graph import OrganizationGraphProjection
            from rationalevault.knowledge.factory import get_knowledge_provider

            provider = get_knowledge_provider()
            all_knowledge = provider.get_all_knowledge()
            recent_knowledge_by_project: dict[str, list[Any]] = {}
            for pid in organization_state.project_ids:
                pid_knowledge = [
                    k for k in all_knowledge
                    if getattr(k, "project_id", "") == pid
                ]
                recent_knowledge_by_project[pid] = pid_knowledge[:10]

            activity = OrganizationActivityProjection.project(
                project_ids=organization_state.project_ids,
                recent_events_by_project={},
                recent_knowledge_by_project=recent_knowledge_by_project,
                recent_memories_by_project={},
                org_state=organization_state,
                activity_window_hours=72,
            )
            org_graph_state = OrganizationGraphProjection.project(organization_state)
            organization_continuation_state = OrganizationContinuationProjection.project(
                org_state=organization_state,
                graph_state=org_graph_state,
                activity_state=activity,
            )
        except Exception:
            organization_continuation_state = None

    # 1. Analyze query
    t_analysis_start = time.perf_counter()
    intent = analyze_query(query)
    if profile is not None:
        intent = QueryIntent(
            profile=profile,
            keywords=intent.keywords,
            intent=intent.intent,
        )
    t_analysis_end = time.perf_counter()

    # 2. Retrieve memory citations
    t_memory_start = time.perf_counter()
    memory_citations: list[Any] = []
    try:
        memory_citations, _ = retrieve_ranked_citations(query, limit=memory_limit)
    except Exception:
        memory_citations = []
    t_memory_end = time.perf_counter()

    # 3. Retrieve knowledge citations
    t_knowledge_start = time.perf_counter()
    knowledge_citations: list[Any] = []
    try:
        knowledge_citations, _ = retrieve_ranked_knowledge_citations(
            query, limit=knowledge_limit, intent=intent,
            project_id=str(project_id) if project_id else None,
        )
    except Exception:
        knowledge_citations = []
    t_knowledge_end = time.perf_counter()

    # 4. Retrieve relevant events
    t_event_start = time.perf_counter()
    event_contexts: list[EventContext] = []
    if project_id is not None:
        event_contexts = _retrieve_relevant_events(
            project_id, query, intent.keywords, limit=event_limit
        )
    t_event_end = time.perf_counter()

    # 5. Blend all sources
    t_blend_start = time.perf_counter()
    citations = _blend_citations(
        memory_citations=memory_citations,
        knowledge_citations=knowledge_citations,
        event_contexts=event_contexts,
        profile=intent.profile,
        total_limit=total_slices,
        mode=mode,
    )
    t_blend_end = time.perf_counter()

    # 6. Assemble ContextPackage
    t_end = time.perf_counter()

    source_counts = {
        "events": sum(1 for c in citations if c.source_type == "event"),
        "memories": sum(1 for c in citations if c.source_type == "memory"),
        "knowledge": sum(1 for c in citations if c.source_type == "knowledge"),
    }

    timing = {
        "query_analysis_ms": (t_analysis_end - t_analysis_start) * 1000.0,
        "memory_retrieval_ms": (t_memory_end - t_memory_start) * 1000.0,
        "knowledge_retrieval_ms": (t_knowledge_end - t_knowledge_start) * 1000.0,
        "event_retrieval_ms": (t_event_end - t_event_start) * 1000.0,
        "blending_ms": (t_blend_end - t_blend_start) * 1000.0,
        "total_ms": (t_end - t_start) * 1000.0,
    }

    inclusion_reasons = _build_inclusion_reasons(intent.profile, source_counts)

    context_id = hashlib.sha256(
        f"{query}:{intent.profile.value}:{datetime.now().isoformat()}".encode()
    ).hexdigest()[:16]

    return ContextPackage(
        context_id=context_id,
        query=query,
        profile=intent.profile.value,
        created_at=datetime.now().isoformat(),
        citations=citations,
        inclusion_reasons=inclusion_reasons,
        source_counts=source_counts,
        timing=timing,
        mode=mode.value,
        continuation_state=continuation_state,
        knowledge_state=knowledge_state,
        graph_state=graph_state,
        cross_project_state=cross_project_state,
        organization_state=organization_state,
        organization_continuation_state=organization_continuation_state,
        retrieval_plan=plan,
    )

