from __future__ import annotations

from typing import Optional
from uuid import UUID

from rationalevault.mcp.server import server
from rationalevault.schema.events import EventMetadata, EventType, EventRecord
from rationalevault.cognitive_head.compiler import compile_cognitive_head
from rationalevault.knowledge.context_compiler import compile_context, ContextMode
from rationalevault.memory.query_analyzer import RetrievalProfile
from rationalevault.memory.retrieval import retrieve_ranked_citations
from rationalevault.knowledge.knowledge_retrieval import retrieve_ranked_knowledge_citations
from rationalevault.compilers.registry import get_context_compiler
from rationalevault.db.event_store import EventStore


def _record_to_dict(rec: EventRecord) -> dict:
    return {
        "event_sequence": rec.event_sequence,
        "id": str(rec.id),
        "project_id": str(rec.project_id),
        "stream_id": rec.stream_id,
        "version": rec.version,
        "event_type": rec.event_type.value if hasattr(rec.event_type, "value") else str(rec.event_type),
        "metadata": rec.metadata.to_dict() if rec.metadata else {},
        "payload": rec.payload,
        "parent_id": str(rec.parent_id) if rec.parent_id else None,
        "recorded_at": rec.recorded_at.isoformat() if rec.recorded_at else None,
    }


# ── READ TOOLS ───────────────────────────────────────────────────────────────

@server.tool()
def get_cognitive_head(project_id: str) -> dict:
    """Compile and return the current project state (active tasks, decisions, open questions)."""
    pid = UUID(project_id)
    head = compile_cognitive_head(pid)
    return head.to_dict()


@server.tool()
def get_context(
    query: str,
    project_id: Optional[str] = None,
    profile: Optional[str] = None,
    mode: str = "standard"
) -> dict:
    """Compile a unified context package blending events, memories, and knowledge."""
    pid = UUID(project_id) if project_id else None
    prof = RetrievalProfile(profile) if profile else None
    ctx_mode = ContextMode(mode)
    package = compile_context(query, project_id=pid, profile=prof, mode=ctx_mode)
    return package.to_dict()


@server.tool()
def continue_project(project_id: str, agent: str = "claude") -> str:
    """Retrieve continuation context and render the Where I Left Off block for the given agent."""
    pid = UUID(project_id)
    package = compile_context("continue", project_id=pid, mode=ContextMode.CONTINUATION)
    compiler = get_context_compiler(agent)
    output = compiler.compile(package)
    return output.rendered_content


@server.tool()
def search_memories(query: str, limit: int = 10) -> list[dict]:
    """Search for relevant compiled memories matching the query."""
    citations, _ = retrieve_ranked_citations(query, limit=limit)
    return [c.to_dict() for c in citations]


@server.tool()
def search_knowledge(query: str, limit: int = 10, project_id: Optional[str] = None) -> list[dict]:
    """Search for relevant synthesized knowledge objects matching the query."""
    citations, _ = retrieve_ranked_knowledge_citations(
        query, limit=limit, project_id=project_id,
    )
    return [c.to_dict() for c in citations]


@server.tool()
def search_embeddings(query: str, k: int = 10) -> list[dict]:
    """Semantic search over knowledge embeddings using FAISS.

    Requires 'rationalevault[embed]' to be installed.
    Returns a list of search results with node_id, score, and metadata.
    """
    from rationalevault.embedding.provider import SentenceTransformerProvider
    from rationalevault.embedding.builder import EmbeddingBuilder
    from rationalevault.embedding.faiss_adapter import FAISSAdapter
    from rationalevault.embedding.state import EmbeddingState
    from rationalevault.embedding.canonicalizer import CanonicalKnowledgeRenderer
    from rationalevault.knowledge.factory import get_knowledge_provider

    provider = SentenceTransformerProvider()
    builder = EmbeddingBuilder(provider)
    adapter = FAISSAdapter(builder)

    knowledge_provider = get_knowledge_provider()
    knowledge = knowledge_provider.get_all_knowledge()

    state = EmbeddingState(
        provider=provider.provider_name,
        model=provider.model_name,
        dimension=provider.dimension,
    )

    for kn in knowledge:
        canonical_text = CanonicalKnowledgeRenderer.render(
            node_id=kn.id,
            title=kn.title,
            content=kn.content,
            knowledge_type=kn.knowledge_type.value,
            tags=kn.tags,
            importance=kn.importance,
            domain=kn.knowledge_domain.value,
        )
        content_hash = CanonicalKnowledgeRenderer.content_hash(canonical_text)
        state.nodes[kn.id] = {
            "canonical_text": canonical_text,
            "content_hash": content_hash,
        }

    adapter.build(state)
    results = adapter.search(query, k=k)

    return [
        {
            "id": r.id,
            "score": r.score,
            "metadata": r.payload,
        }
        for r in results
    ]


@server.tool()
def get_timeline(
    limit: int = 50,
    category: str | None = None,
) -> list[dict]:
    """Retrieve chronological narrative entries.

    Returns timeline entries showing the system's evolution over time.
    Each entry normalizes heterogeneous events into a uniform format
    with sequence, event_type, category, actor, and summary.
    """
    from rationalevault.timeline.projection import TimelineProjection
    from rationalevault.timeline.state import TimelineState, TimelineCategory

    proj = TimelineProjection()

    try:
        from rationalevault.knowledge.factory import get_knowledge_provider
        knowledge_provider = get_knowledge_provider()
        knowledge = knowledge_provider.get_all_knowledge()

        events = []
        for k in knowledge:
            from rationalevault.schema.events import EventRecord, EventType, EventMetadata
            from uuid import uuid4

            events.append(EventRecord(
                event_sequence=len(events) + 1,
                id=uuid4(),
                project_id=uuid4(),
                stream_id="knowledge",
                version=1,
                event_type=EventType.KNOWLEDGE_CREATED,
                metadata=EventMetadata(actor="mcp", source="timeline"),
                payload={
                    "knowledge_id": k.id,
                    "title": k.title,
                    "content": k.content,
                    "knowledge_type": k.knowledge_type.value,
                    "tags": k.tags,
                    "importance": k.importance,
                    "knowledge_domain": k.knowledge_domain.value,
                },
                parent_id=None,
                recorded_at=None,
            ))

        state = proj.reduce(events) if events else TimelineState()
    except Exception:
        state = TimelineState()

    entries = state.entries

    if category:
        try:
            cat = TimelineCategory(category)
            entries = [e for e in entries if e.category == cat]
        except ValueError:
            return [{"error": f"Unknown category: {category}"}]

    entries = entries[-limit:]

    return [
        {
            "sequence": e.sequence,
            "event_type": e.event_type.value,
            "category": e.category.value,
            "actor": e.actor,
            "subject_entity": e.subject_entity,
            "summary": e.summary,
        }
        for e in entries
    ]


@server.tool()
def get_warnings(
    limit: int = 50,
    severity: str | None = None,
    action: str | None = None,
    project_id: str | None = None,
) -> list[dict]:
    """Retrieve governance warnings representing policy matches.

    Checks derived facts and recommendations against registered policy conditions.
    Supports filtering by severity (info, warning, critical) and action (notify, block, suggest, log).
    """
    from datetime import datetime
    from rationalevault.governance.projection import GovernanceProjection
    from rationalevault.governance.runtime import GovernanceRuntime, DefaultEvidenceProvider
    from rationalevault.governance.state import (
        GovernanceState,
        GovernanceSeverity,
        GovernanceAction,
    )
    from rationalevault.projection_platform.context import DependencyReader
    from rationalevault.recommendation.projection import RecommendationProjection
    from rationalevault.projection_platform.manager import ProjectionManager
    from rationalevault.projection_platform.registry import ProjectionRegistry
    from rationalevault.projection_platform.compiler import ProjectionCompiler

    runtime = GovernanceRuntime()
    state = None
    rec_state = None

    if project_id:
        from uuid import UUID
        pid = UUID(project_id)
        # Setup compiler & registry with default deps
        registry = ProjectionRegistry()
        registry.register(GovernanceProjection())
        registry.register(RecommendationProjection())
        
        # TODO: Remove DummyProjection adapter once KnowledgeProjection and EmbeddingProjection
        # are first-class ProjectionPlatform projections. This is a temporary bridge to satisfy
        # ProjectionCompiler dependency resolution until they are fully migrated.
        from rationalevault.projection_platform.protocols import Projection
        from rationalevault.projection_platform.models import ProjectionMetadata, ProjectionHealth, ProjectionCapabilities, EventSelector
        
        class DummyProjection(Projection):
            def __init__(self, id: str):
                self._id = id
            @property
            def metadata(self) -> ProjectionMetadata:
                return ProjectionMetadata(id=self._id, version=1, description="Dummy", schema_version=1, consumed_events=EventSelector(types=frozenset()), capabilities=ProjectionCapabilities())
            def initialize(self, ctx) -> None: pass
            def reduce(self, events, initial_state=None): return None
            def serialize(self, state): return {}
            def deserialize(self, payload): return None
            def health(self) -> ProjectionHealth: return ProjectionHealth.READY
            def shutdown(self) -> None: pass

        registry.register(DummyProjection("knowledge"))
        registry.register(DummyProjection("embedding"))
        
        # ProjectionManager
        compiler = ProjectionCompiler(registry=registry)
        manager = ProjectionManager(registry, compiler)
        
        try:
            state = manager.get_projection_state(pid, "governance")
            rec_state = manager.get_projection_state(pid, "recommendation")
        except Exception:
            pass

    if state is None:
        state = GovernanceState()

    if rec_state is None:
        from rationalevault.recommendation.state import RecommendationState
        rec_state = RecommendationState()


    # Register default rule if empty and in ephemeral mode (no project_id)
    if not project_id and not state.rules:
        from rationalevault.governance.state import (
            GovernanceRule,
            GovernanceRuleMetadata,
            GovernanceCondition,
        )
        from rationalevault.recommendation.state import RecommendationCategory
        default_rule = GovernanceRule(
            metadata=GovernanceRuleMetadata(
                id="default_risk_notify",
                version=1,
                description="Default policy to notify about risks",
                severity=GovernanceSeverity.WARNING,
                action=GovernanceAction.NOTIFY,
            ),
            condition=GovernanceCondition(
                categories={RecommendationCategory.RISK},
                minimum_priority=0.4,
            ),
        )
        state.rules.append(default_rule)
    elif project_id and not state.rules:
        # Empty policy mode
        pass


    reader = DependencyReader()
    reader.set("recommendation", rec_state)
    provider = DefaultEvidenceProvider(reader)

    evals = runtime.evaluate_rules(state, provider)
    warnings = runtime.generate_warnings(state, evals, query_time=datetime.now())

    sev = None
    if severity:
        try:
            sev = GovernanceSeverity(severity)
        except ValueError:
            pass

    act = None
    if action:
        try:
            act = GovernanceAction(action)
        except ValueError:
            pass

    results = runtime.search(warnings, severity=sev, action=act, limit=limit)
    return [
        {
            "id": w.id,
            "rule_id": w.rule_id,
            "rule_version": w.rule_version,
            "target_entity": w.target_entity,
            "severity": w.severity.value,
            "action": w.action.value,
            "message": w.message,
            "evidence": w.evidence,
            "created_at": w.created_at.isoformat(),
        }
        for w in results
    ]


@server.tool()
def get_recommendations(
    limit: int = 10,
    entity: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Retrieve derived recommendations from event history.

    Returns recommendations ranked by intrinsic priority.
    Recommendations are deterministic facts derived from events,
    not query-dependent suggestions.
    """
    from rationalevault.recommendation.projection import (
        RecommendationProjection,
    )
    from rationalevault.recommendation.runtime import (
        RecommendationRuntime,
    )
    from rationalevault.recommendation.state import (
        RecommendationState, RecommendationCategory,
    )

    proj = RecommendationProjection()
    runtime = RecommendationRuntime()

    try:
        from rationalevault.knowledge.factory import (
            get_knowledge_provider,
        )
        knowledge_provider = get_knowledge_provider()
        knowledge = knowledge_provider.get_all_knowledge()

        events = []
        for k in knowledge:
            from rationalevault.schema.events import (
                EventRecord, EventType, EventMetadata,
            )
            from uuid import uuid4

            events.append(EventRecord(
                event_sequence=len(events) + 1,
                id=uuid4(),
                project_id=uuid4(),
                stream_id="knowledge",
                version=1,
                event_type=EventType.KNOWLEDGE_CREATED,
                metadata=EventMetadata(
                    actor="mcp", source="recommendation",
                ),
                payload={
                    "knowledge_id": k.id,
                    "title": k.title,
                    "content": k.content,
                    "knowledge_type": k.knowledge_type.value,
                    "tags": k.tags,
                    "importance": k.importance,
                    "knowledge_domain": k.knowledge_domain.value,
                },
                parent_id=None,
                recorded_at=None,
            ))

        state = (
            proj.reduce(events)
            if events
            else RecommendationState()
        )
    except Exception:
        state = RecommendationState()

    cat = None
    if category:
        try:
            cat = RecommendationCategory(category)
        except ValueError:
            return [{"error": f"Unknown category: {category}"}]

    from datetime import datetime
    from rationalevault.recommendation.state import (
        RecommendationQueryContext,
    )
    ctx = RecommendationQueryContext(query_time=datetime.now())

    results = runtime.search(
        state,
        entity=entity,
        category=cat,
        k=limit,
        context=ctx,
    )

    return [
        {
            "id": r.recommendation.id,
            "rule_id": r.recommendation.rule_id,
            "rule_version": r.recommendation.rule_version,
            "target_entity": r.recommendation.target_entity,
            "category": r.recommendation.category.value,
            "priority": r.recommendation.priority,
            "final_score": r.final_score,
            "rationale": r.recommendation.rationale,
            "evidence": [
                e.sequence
                for e in r.recommendation.evidence
            ],
        }
        for r in results
    ]


@server.tool()
def get_project_events(project_id: str, limit: int = 20) -> list[dict]:
    """Get the most recent event records from the ledger for a project."""
    pid = UUID(project_id)
    store = EventStore()
    events = store.get_recent_events(pid, limit=limit)
    return [_record_to_dict(e) for e in events]


# ── WRITE TOOLS ──────────────────────────────────────────────────────────────

@server.tool()
def record_event(
    project_id: str,
    stream_id: str,
    event_type: str,
    payload: dict,
    actor: str,
    source: str,
    session_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> dict:
    """Append a validated event record directly to the project event stream."""
    # Enforce EventType validation
    try:
        ev_type = EventType(event_type)
    except ValueError:
        valid_types = [t.value for t in EventType]
        raise ValueError(
            f"Invalid event_type '{event_type}'. Must be one of: {', '.join(valid_types)}"
        )

    pid = UUID(project_id)
    par_id = UUID(parent_id) if parent_id else None

    # Construct metadata
    meta = EventMetadata(
        actor=actor,
        source=source,
    )
    if session_id:
        meta.session_id = session_id
    if correlation_id:
        meta.correlation_id = correlation_id

    store = EventStore()
    record = store.append_event(
        project_id=pid,
        stream_id=stream_id,
        event_type=ev_type,
        payload=payload,
        metadata=meta,
        parent_id=par_id,
    )
    return _record_to_dict(record)


@server.tool()
def record_task_progress(
    project_id: str,
    task_id: str,
    note: str,
    actor: str,
    source: str,
    session_id: Optional[str] = None,
) -> dict:
    """Emit a TASK_PROGRESS_NOTED event for a task, appending a progress note."""
    pid = UUID(project_id)
    meta = EventMetadata(
        actor=actor,
        source=source,
    )
    if session_id:
        meta.session_id = session_id

    store = EventStore()
    record = store.append_event(
        project_id=pid,
        stream_id="tasks",
        event_type=EventType.TASK_PROGRESS_NOTED,
        payload={"task_id": task_id, "note": note},
        metadata=meta,
    )
    return _record_to_dict(record)


@server.tool()
def search_cross_project(
    query: str,
    project_id: Optional[str] = None,
    transferability_filter: Optional[list[str]] = None,
) -> dict:
    """Discover transferable knowledge from registered projects.

    Searches across all registered projects in the ProjectRegistry,
    returning knowledge objects that are REUSABLE or ORGANIZATIONAL.
    """
    from rationalevault.knowledge.project_registry import ProjectRegistry
    from rationalevault.knowledge.factory import get_knowledge_provider
    from rationalevault.projections.cross_project import CrossProjectProjection

    registry = ProjectRegistry.load()
    projects = registry.list_projects()
    if not projects:
        return {"error": "No registered projects", "transferable_knowledge": []}

    current_id = project_id or ""
    provider = get_knowledge_provider()
    current_knowledge = provider.get_all_knowledge()

    target_knowledge: dict[str, list] = {}
    for entry in projects:
        if entry.id == current_id:
            continue
        try:
            from rationalevault.knowledge.store import SQLiteKnowledgeProvider
            from pathlib import Path as _Path
            target_store = SQLiteKnowledgeProvider(db_path=str(_Path(entry.path) / ".rationalevault" / "knowledge.db"))
            target_knowledge[entry.id] = target_store.get_all_knowledge()
        except Exception:
            target_knowledge[entry.id] = []

    state = CrossProjectProjection.project(
        current_project_id=current_id,
        current_knowledge=current_knowledge,
        target_knowledge=target_knowledge,
        query=query,
        transferability_filter=transferability_filter,
    )

    return state.to_dict()


@server.tool()
def get_organization_state() -> dict:
    """Get the organizational knowledge visibility state across all registered projects."""
    from rationalevault.knowledge.project_registry import ProjectRegistry
    from rationalevault.projections.cross_project import CrossProjectProjection
    from rationalevault.organization.projection import OrganizationProjection

    registry = ProjectRegistry.load()
    projects = registry.list_projects()
    if not projects:
        return {"error": "No registered projects", "project_ids": []}

    knowledge_by_project: dict = {}
    for entry in projects:
        try:
            from rationalevault.knowledge.store import SQLiteKnowledgeProvider
            from pathlib import Path as _Path
            store = SQLiteKnowledgeProvider(db_path=str(_Path(entry.path) / ".rationalevault" / "knowledge.db"))
            knowledge_by_project[entry.id] = store.get_all_knowledge()
        except Exception:
            knowledge_by_project[entry.id] = []

    cross_states: dict = {}
    for entry in projects:
        targets = {pid: klist for pid, klist in knowledge_by_project.items() if pid != entry.id}
        cross_states[entry.id] = CrossProjectProjection.project(
            current_project_id=entry.id,
            current_knowledge=knowledge_by_project.get(entry.id, []),
            target_knowledge=targets,
        )

    state = OrganizationProjection.project(
        registry=registry,
        cross_project_states=cross_states,
        knowledge_by_project=knowledge_by_project,
    )

    return state.to_dict()


@server.tool()
def build_retrieval_plan(query: str) -> dict:
    """Build a retrieval plan for a hybrid query.

    Classifies intent, selects projections, and allocates context weights.
    """
    from rationalevault.retrieval.orchestrator import RetrievalOrchestrator

    orch = RetrievalOrchestrator()
    plan = orch.build_plan(query)
    return plan.to_dict()


@server.tool()
def get_organization_graph_state() -> dict:
    """Get the organization graph projection.

    Returns a project-centric graph where nodes are projects
    and edges represent transfer, shared, conflict, and cluster relationships.
    """
    from rationalevault.organization.service import build_org_state_from_registry
    from rationalevault.organization.graph import OrganizationGraphProjection

    org_state, _ = build_org_state_from_registry()
    if org_state is None:
        return {"error": "No registered projects"}

    graph = OrganizationGraphProjection.project(org_state)
    return graph.to_dict()


@server.tool()
def query_organization_graph(project_id: str) -> dict:
    """Query a project node in the organization graph.

    Returns node metadata and all incoming/outgoing edges.
    """
    from rationalevault.organization.service import build_org_state_from_registry
    from rationalevault.organization.graph import OrganizationGraphProjection

    org_state, _ = build_org_state_from_registry()
    if org_state is None:
        return {"error": "No registered projects"}

    graph = OrganizationGraphProjection.project(org_state)

    pid = project_id
    if pid not in graph.nodes:
        matches = [n for n in graph.nodes if n.startswith(pid)]
        if len(matches) == 1:
            pid = matches[0]
        else:
            return {"error": f"Project '{project_id}' not found", "available": sorted(graph.nodes)}

    node = graph.nodes[pid]
    out_edges = graph.adjacency.get(pid, [])
    in_edges = graph.reverse_adjacency.get(pid, [])
    return {
        "node": {
            "project_id": node.project_id,
            "knowledge_count": node.knowledge_count,
            "transferable_count": node.transferable_count,
            "shared_count": node.shared_count,
            "conflict_count": node.conflict_count,
            "is_cluster_center": node.is_cluster_center,
        },
        "outgoing_edges": [{
            "target": e.target,
            "relation_type": e.relation_type.value,
            "weight": e.weight,
            "confidence": e.confidence,
        } for e in out_edges],
        "incoming_edges": [{
            "source": e.source,
            "relation_type": e.relation_type.value,
            "weight": e.weight,
            "confidence": e.confidence,
        } for e in in_edges],
        "flow_balance": graph.knowledge_flow_balance.get(pid, 0),
    }


@server.tool()
def get_organization_activity(window_hours: int = 72) -> dict:
    """Get the organization activity state.

    Pure temporal observation layer. Shows project activity, recent transfers,
    recent conflicts, and recently created/updated knowledge.
    """
    from rationalevault.organization.service import build_org_state_from_registry
    from rationalevault.organization.activity import OrganizationActivityProjection
    from rationalevault.knowledge.factory import get_knowledge_provider

    org_state, _ = build_org_state_from_registry()
    if org_state is None:
        return {"error": "No registered projects"}

    provider = get_knowledge_provider()
    all_knowledge = provider.get_all_knowledge()
    from collections import defaultdict
    knowledge_by_pid: dict[str, list] = defaultdict(list)
    for k in all_knowledge:
        knowledge_by_pid[getattr(k, "project_id", "")].append(k)
    recent_knowledge_by_project = {pid: knowledge_by_pid[pid][:10] for pid in org_state.project_ids}

    activity = OrganizationActivityProjection.project(
        project_ids=org_state.project_ids,
        recent_events_by_project={},
        recent_knowledge_by_project=recent_knowledge_by_project,
        recent_memories_by_project={},
        org_state=org_state,
        activity_window_hours=window_hours,
    )
    return activity.to_dict()


@server.tool()
def get_organization_continuation(window_hours: int = 72) -> dict:
    """Get the organization continuation state.

    Interpretation of organizational activity. Shows projects needing attention,
    organizational next actions, and a continuation summary.
    """
    from rationalevault.organization.service import build_org_state_from_registry
    from rationalevault.organization.activity import OrganizationActivityProjection
    from rationalevault.organization.continuation import OrganizationContinuationProjection
    from rationalevault.organization.graph import OrganizationGraphProjection
    from rationalevault.knowledge.factory import get_knowledge_provider

    org_state, _ = build_org_state_from_registry()
    if org_state is None:
        return {"error": "No registered projects"}

    provider = get_knowledge_provider()
    all_knowledge = provider.get_all_knowledge()
    from collections import defaultdict
    knowledge_by_pid2: dict[str, list] = defaultdict(list)
    for k in all_knowledge:
        knowledge_by_pid2[getattr(k, "project_id", "")].append(k)
    recent_knowledge_by_project = {pid: knowledge_by_pid2[pid][:10] for pid in org_state.project_ids}

    activity = OrganizationActivityProjection.project(
        project_ids=org_state.project_ids,
        recent_events_by_project={},
        recent_knowledge_by_project=recent_knowledge_by_project,
        recent_memories_by_project={},
        org_state=org_state,
        activity_window_hours=window_hours,
    )
    graph = OrganizationGraphProjection.project(org_state)
    cont = OrganizationContinuationProjection.project(org_state, graph, activity)
    return cont.to_dict()


@server.tool()
def get_recommendations() -> dict:
    """Get organizational recommendations.

    Returns a RecommendationSet with prioritized recommendations
    derived from organizational state, graph, and continuation state.
    """
    from rationalevault.organization.service import build_org_state_from_registry
    from rationalevault.organization.activity import OrganizationActivityProjection
    from rationalevault.organization.continuation import OrganizationContinuationProjection
    from rationalevault.organization.graph import OrganizationGraphProjection
    from rationalevault.recommendations.engine import RecommendationEngine
    from rationalevault.knowledge.factory import get_knowledge_provider

    org_state, _ = build_org_state_from_registry()
    if org_state is None:
        return {"error": "No registered projects", "recommendations": [], "recommendation_count": 0}

    provider = get_knowledge_provider()
    all_knowledge = provider.get_all_knowledge()
    from collections import defaultdict
    knowledge_by_pid3: dict[str, list] = defaultdict(list)
    for k in all_knowledge:
        knowledge_by_pid3[getattr(k, "project_id", "")].append(k)
    recent_knowledge_by_project = {pid: knowledge_by_pid3[pid][:10] for pid in org_state.project_ids}

    activity = OrganizationActivityProjection.project(
        project_ids=org_state.project_ids,
        recent_events_by_project={},
        recent_knowledge_by_project=recent_knowledge_by_project,
        recent_memories_by_project={},
        org_state=org_state,
        activity_window_hours=72,
    )
    graph = OrganizationGraphProjection.project(org_state)
    cont = OrganizationContinuationProjection.project(org_state, graph, activity)

    result = RecommendationEngine.generate(
        org_state=org_state,
        graph_state=graph,
        activity_state=activity,
    )
    return result.to_dict()


@server.tool()
def get_project_recommendations(project_id: str) -> dict:
    """Get organizational recommendations filtered to a specific project.

    Args:
        project_id: The project to filter recommendations for.
    """
    result = get_recommendations()
    if "error" in result:
        return result
    filtered = [
        r for r in result.get("recommendations", [])
        if project_id in r.get("affected_projects", [])
    ]
    return {
        "compiled_at": result.get("compiled_at", ""),
        "recommendations": filtered,
        "recommendation_count": len(filtered),
        "attention_load": result.get("attention_load", 0.0),
    }


def retrieval_dashboard() -> dict:
    """Return retrieval telemetry dashboard as a dict."""
    from rationalevault.telemetry.metrics import get_collector

    snap = get_collector().snapshot()
    return {
        "total_requests": snap.total_requests,
        "avg_total_ms": snap.avg_total_ms,
        "p50_total_ms": snap.p50_total_ms,
        "p95_total_ms": snap.p95_total_ms,
        "p99_total_ms": snap.p99_total_ms,
        "avg_provider_latency_ms": snap.avg_provider_latency_ms,
        "avg_candidate_count": snap.avg_candidate_count,
        "avg_retrieved_count": snap.avg_retrieved_count,
        "profile_distribution": snap.profile_distribution,
        "stage_averages": snap.stage_averages,
    }
