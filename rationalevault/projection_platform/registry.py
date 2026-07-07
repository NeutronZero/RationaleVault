"""ProjectionRegistry — explicit registration and validation."""
from __future__ import annotations


from rationalevault.projection_platform.models import ProjectionMetadata
from rationalevault.projection_platform.protocols import Projection


class ProjectionNotFoundError(Exception):
    """Raised when a required projection is not registered."""


class CyclicDependencyError(Exception):
    """Raised when a cycle is detected in projection dependencies."""


class ProjectionRegistry:
    """Manages projection registration and dependency validation.

    No auto-discovery. Explicit registration ensures deterministic startup.
    """

    def __init__(self) -> None:
        self._projections: dict[str, Projection] = {}
        self._frozen: bool = False

    def register(self, projection: Projection) -> None:
        """Register a projection. Raises if frozen."""
        if self._frozen:
            raise RuntimeError("Registry is frozen; cannot register new projections")
        meta = projection.metadata
        if meta.id in self._projections:
            raise ValueError(f"Projection '{meta.id}' already registered")
        self._projections[meta.id] = projection

    def get(self, projection_id: str) -> Projection:
        """Return a registered projection by ID."""
        if projection_id not in self._projections:
            raise ProjectionNotFoundError(
                f"Projection '{projection_id}' not found"
            )
        return self._projections[projection_id]

    def all(self) -> list[Projection]:
        """Return all registered projections."""
        return list(self._projections.values())

    def metadata(self, projection_id: str) -> ProjectionMetadata:
        """Return metadata for a registered projection."""
        return self.get(projection_id).metadata

    def freeze(self) -> None:
        """Freeze the registry. Validates dependencies after freezing."""
        self._validate_dependencies()
        self._frozen = True

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    def _validate_dependencies(self) -> None:
        """Validate that all dependencies exist and there are no cycles."""
        ids = set(self._projections.keys())

        # Check all dependencies exist
        for proj in self._projections.values():
            meta = proj.metadata
            for dep in meta.dependencies:
                if dep.projection_id not in ids and not dep.optional:
                    raise ProjectionNotFoundError(
                        f"Projection '{meta.id}' requires '{dep.projection_id}' "
                        f"which is not registered"
                    )

        # Check for cycles (DFS)
        visited: set[str] = set()
        path: set[str] = set()

        def _dfs(node_id: str) -> None:
            if node_id in path:
                raise CyclicDependencyError(
                    f"Cyclic dependency detected involving '{node_id}'"
                )
            if node_id in visited:
                return
            path.add(node_id)
            visited.add(node_id)
            if node_id in self._projections:
                meta = self._projections[node_id].metadata
                for dep in meta.dependencies:
                    if dep.projection_id in ids:
                        _dfs(dep.projection_id)
            path.discard(node_id)

        for proj_id in ids:
            _dfs(proj_id)
