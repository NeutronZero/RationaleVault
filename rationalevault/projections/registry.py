from __future__ import annotations
from rationalevault.projections.base import BaseProjection, ProjectionKind

class CircularDependencyError(ValueError):
    """Raised when a circular dependency is detected in the projection graph."""
    pass

class MissingDependencyError(ValueError):
    """Raised when a projection references a dependency that is not registered."""
    pass

class DuplicateProjectionError(ValueError):
    """Raised when a duplicate registration or name collision occurs."""
    pass

class InvalidDependencyKindError(ValueError):
    """Raised when a projection kind boundary rule is violated."""
    pass

class ProjectionRegistry:
    """Central registry and dependency manager for RationaleVault projections."""

    def __init__(self) -> None:
        self._projections: dict[str, type[BaseProjection]] = {}
        self._classes: set[type[BaseProjection]] = set()

    def register(self, projection_cls: type[BaseProjection]) -> None:
        """Registers a projection class. Performs validation checks on registration."""
        if not issubclass(projection_cls, BaseProjection):
            raise TypeError("Must subclass BaseProjection")

        name = projection_cls.projection_name
        if not name:
            raise ValueError("Projection must declare a non-empty projection_name")

        if projection_cls in self._classes:
            raise DuplicateProjectionError(f"Class '{projection_cls.__name__}' is already registered.")

        if name in self._projections:
            colliding_cls = self._projections[name]
            raise DuplicateProjectionError(
                f"Projection name collision: '{name}' is registered by both "
                f"'{colliding_cls.__name__}' and '{projection_cls.__name__}'."
            )

        self._projections[name] = projection_cls
        self._classes.add(projection_cls)

    def get_projection(self, target: str | type[BaseProjection]) -> type[BaseProjection]:
        """Looks up a projection class by name or class reference."""
        if isinstance(target, str):
            if target not in self._projections:
                raise KeyError(f"Projection '{target}' is not registered.")
            return self._projections[target]
        else:
            if target not in self._classes:
                raise KeyError(f"Projection class '{target.__name__}' is not registered.")
            return target

    def get_all(self) -> dict[str, type[BaseProjection]]:
        """Returns a copy of all registered projections."""
        return dict(self._projections)

    def validate(self) -> None:
        """Executes all validation phases: duplicates, missing dependencies, kind boundary rules, and cycles."""
        self._validate_names_and_classes()
        self._validate_dependencies()
        self._validate_kinds()
        self._validate_cycles()

    def _validate_names_and_classes(self) -> None:
        # Covered during registration, but we verify consistency here.
        names = [cls.projection_name for cls in self._classes]
        if len(names) != len(set(names)):
            raise DuplicateProjectionError("Duplicate projection names detected.")

    def _validate_dependencies(self) -> None:
        for cls in self._classes:
            for dep in cls.dependencies:
                if dep not in self._classes:
                    raise MissingDependencyError(
                        f"Projection '{cls.projection_name}' depends on '{dep.projection_name or dep.__name__}', "
                        "which is not registered."
                    )

    def _validate_kinds(self) -> None:
        for cls in self._classes:
            kind = cls.projection_kind
            if kind == ProjectionKind.BASE:
                if cls.dependencies:
                    raise InvalidDependencyKindError(
                        f"Base projection '{cls.projection_name}' must not have any dependencies."
                    )
            elif kind == ProjectionKind.DERIVED:
                for dep in cls.dependencies:
                    if dep.projection_kind == ProjectionKind.COMPOSITE:
                        raise InvalidDependencyKindError(
                            f"Derived projection '{cls.projection_name}' cannot depend on composite "
                            f"projection '{dep.projection_name}'."
                        )

    def _validate_cycles(self) -> None:
        # Iterative cycle detection using stack state tracking to avoid deep recursive calls
        visited = {cls: 0 for cls in self._classes} # 0=unvisited, 1=visiting, 2=visited
        
        for root in self._classes:
            if visited[root] != 0:
                continue
            
            # Stack holds tuples of (node, list of child dependencies remaining to visit)
            stack: list[tuple[type[BaseProjection], list[type[BaseProjection]]]] = []
            stack.append((root, list(root.dependencies)))
            visited[root] = 1 # visiting
            
            while stack:
                curr, children = stack[-1]
                if not children:
                    visited[curr] = 2 # fully visited
                    stack.pop()
                    continue
                
                next_child = children.pop()
                if visited[next_child] == 1:
                    # Found a cycle back to something currently being visited
                    raise CircularDependencyError(
                        f"Circular dependency detected containing: '{curr.projection_name}' -> '{next_child.projection_name}'."
                    )
                elif visited[next_child] == 0:
                    visited[next_child] = 1 # visiting
                    stack.append((next_child, list(next_child.dependencies)))

    def topological_sort(self) -> list[type[BaseProjection]]:
        """Resolves projection execution order. Validates graph before computing order.
        
        Tie-breaking prioritizes build_priority (ascending), then projection_name (alphabetical ascending).
        """
        self.validate()
        return self._compute_order()

    def _compute_order(self) -> list[type[BaseProjection]]:
        # Kahn's algorithm with deterministic tie-breaking.
        # Nodes: the projection classes.
        # Edges: dependency -> projection.
        # In-degree of projection is the number of dependencies.
        in_degree = {cls: len(cls.dependencies) for cls in self._classes}
        
        # Build adjacency mapping: dependency -> dependents list
        adj: dict[type[BaseProjection], list[type[BaseProjection]]] = {cls: [] for cls in self._classes}
        for cls in self._classes:
            for dep in cls.dependencies:
                adj[dep].append(cls)

        # Initialize ready set (in-degree == 0)
        ready = [cls for cls, deg in in_degree.items() if deg == 0]
        
        order = []
        
        while ready:
            # Sort ready list: build_priority ASC, then projection_name ASC
            ready.sort(key=lambda c: (c.build_priority, c.projection_name))
            curr = ready.pop(0)
            order.append(curr)
            
            for child in adj[curr]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    ready.append(child)

        return order
