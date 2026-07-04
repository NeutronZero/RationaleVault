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
    from rationalevault.cli.main import _build_org_state_from_registry
    from rationalevault.organization.graph import OrganizationGraphProjection

    org_state, _ = _build_org_state_from_registry()
    if org_state is None:
        return {"error": "No registered projects"}

    graph = OrganizationGraphProjection.project(org_state)
    return graph.to_dict()


@server.tool()
def query_organization_graph(project_id: str) -> dict:
    """Query a project node in the organization graph.

    Returns node metadata and all incoming/outgoing edges.
    """
    from rationalevault.cli.main import _build_org_state_from_registry
    from rationalevault.organization.graph import OrganizationGraphProjection

    org_state, _ = _build_org_state_from_registry()
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
    from rationalevault.cli.main import _build_org_state_from_registry
    from rationalevault.organization.activity import OrganizationActivityProjection
    from rationalevault.knowledge.factory import get_knowledge_provider

    org_state, _ = _build_org_state_from_registry()
    if org_state is None:
        return {"error": "No registered projects"}

    provider = get_knowledge_provider()
    all_knowledge = provider.get_all_knowledge()
    recent_knowledge_by_project: dict[str, list] = {}
    for pid in org_state.project_ids:
        pid_knowledge = [k for k in all_knowledge if getattr(k, "project_id", "") == pid]
        recent_knowledge_by_project[pid] = pid_knowledge[:10]

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
    from rationalevault.cli.main import _build_org_state_from_registry
    from rationalevault.organization.activity import OrganizationActivityProjection
    from rationalevault.organization.continuation import OrganizationContinuationProjection
    from rationalevault.organization.graph import OrganizationGraphProjection
    from rationalevault.knowledge.factory import get_knowledge_provider

    org_state, _ = _build_org_state_from_registry()
    if org_state is None:
        return {"error": "No registered projects"}

    provider = get_knowledge_provider()
    all_knowledge = provider.get_all_knowledge()
    recent_knowledge_by_project: dict[str, list] = {}
    for pid in org_state.project_ids:
        pid_knowledge = [k for k in all_knowledge if getattr(k, "project_id", "") == pid]
        recent_knowledge_by_project[pid] = pid_knowledge[:10]

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
    from rationalevault.cli.main import _build_org_state_from_registry
    from rationalevault.organization.activity import OrganizationActivityProjection
    from rationalevault.organization.continuation import OrganizationContinuationProjection
    from rationalevault.organization.graph import OrganizationGraphProjection
    from rationalevault.recommendations.engine import RecommendationEngine
    from rationalevault.knowledge.factory import get_knowledge_provider

    org_state, _ = _build_org_state_from_registry()
    if org_state is None:
        return {"error": "No registered projects", "recommendations": [], "recommendation_count": 0}

    provider = get_knowledge_provider()
    all_knowledge = provider.get_all_knowledge()
    recent_knowledge_by_project: dict[str, list] = {}
    for pid in org_state.project_ids:
        pid_knowledge = [k for k in all_knowledge if getattr(k, "project_id", "") == pid]
        recent_knowledge_by_project[pid] = pid_knowledge[:10]

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
