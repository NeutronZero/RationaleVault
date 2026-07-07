"""ProjectionManager service."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from rationalevault.projection_platform.compiler import ProjectionCompiler
from rationalevault.projection_platform.registry import ProjectionRegistry


class ProjectionManager:
    """Service to retrieve projection states."""

    def __init__(self, registry: ProjectionRegistry, compiler: ProjectionCompiler) -> None:
        self._registry = registry
        self._compiler = compiler

    def get_projection_state(self, project_id: UUID, projection_id: str) -> Any:
        """Retrieve the current state of a projection, using snapshots if available."""
        # Ensure projection is registered
        self._registry.get(projection_id)
        return self._compiler.compile(project_id, projection_id)
