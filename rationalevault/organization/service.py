"""RationaleVault Organization Service — Shared domain logic for building organization state.

Used by both CLI and MCP to avoid cross-layer dependencies.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def build_org_state_from_registry() -> tuple[Any, Any]:
    """Build OrganizationState from the project registry.

    Returns (OrganizationState, ProjectRegistry) or (None, None) if no projects.
    """
    import yaml
    from rationalevault.knowledge.project_registry import ProjectRegistry
    from rationalevault.projections.cross_project import CrossProjectProjection
    from rationalevault.organization.projection import OrganizationProjection

    registry = ProjectRegistry.load()
    projects = registry.list_projects()
    if not projects:
        return None, None

    current_id = ""
    project_yaml = Path.cwd() / ".rationalevault" / "project.yaml"
    if project_yaml.exists():
        try:
            with open(project_yaml, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            current_id = config.get("project_id", "")
        except Exception:
            pass

    knowledge_by_project: dict = {}
    for entry in projects:
        try:
            from rationalevault.knowledge.store import SQLiteKnowledgeProvider
            store = SQLiteKnowledgeProvider(db_path=str(Path(entry.path) / ".rationalevault" / "knowledge.db"))
            knowledge_by_project[entry.id] = store.get_all_knowledge()
        except Exception:
            knowledge_by_project[entry.id] = []

    cross_states: dict = {}
    for entry in projects:
        if entry.id == current_id:
            continue
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
    return state, registry
