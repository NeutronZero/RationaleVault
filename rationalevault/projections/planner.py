from dataclasses import dataclass
from rationalevault.projections.base import ProjectionKind
from rationalevault.projections.cache import ProjectionCache, CacheKey
from rationalevault.projections.registry import ProjectionRegistry
from rationalevault.projections.fingerprint import compute_composite_fingerprint

@dataclass(frozen=True)
class RebuildMetrics:
    cache_hits: int
    cache_misses: int
    dirty_count: int
    scheduled_count: int

@dataclass(frozen=True)
class RebuildPlan:
    dirty_nodes: set[str]
    ordered_nodes: list[str]
    unchanged_nodes: list[str]
    reasons: dict[str, str]
    metrics: RebuildMetrics
    resolved_fingerprints: dict[str, str]

class RebuildPlanner:
    """Computes a minimal, dependency-aware rebuild execution plan using cached projection state."""

    @staticmethod
    def plan(
        project_id: str,
        current_fingerprints: dict[str, str],
        cache: ProjectionCache,
        registry: ProjectionRegistry
    ) -> RebuildPlan:
        """Determines which projections require compilation based on input fingerprint matches and DAG dependencies."""
        # Retrieve resolved build order (topological sort)
        topo_order = registry.topological_sort()

        resolved_fingerprints: dict[str, str] = {}
        dirty_nodes: set[str] = set()
        reasons: dict[str, str] = {}

        unchanged_nodes: list[str] = []
        ordered_nodes: list[str] = []

        for cls in topo_order:
            name = cls.projection_name
            version = cls.version

            # Compute/resolve fingerprint for the current node
            if cls.projection_kind == ProjectionKind.BASE:
                fp = current_fingerprints.get(name)
                if not fp:
                    raise ValueError(f"Missing input fingerprint for Base projection '{name}'")
            else:
                dep_fps = {dep.projection_name: resolved_fingerprints[dep.projection_name] for dep in cls.dependencies}
                raw_hash = current_fingerprints.get(name) if not cls.dependencies else None
                fp = compute_composite_fingerprint(version, dep_fps, raw_hash)

            resolved_fingerprints[name] = fp

            # Retrieve cached entry
            key = CacheKey(project_id, name, version)
            entry = cache.get(key)

            is_dirty = False
            reason = ""

            # Check if any dependencies are dirty (dirty propagation)
            dirty_deps = [dep.projection_name for dep in cls.dependencies if dep.projection_name in dirty_nodes]

            if dirty_deps:
                is_dirty = True
                reason = f"Dependency changed: {', '.join(dirty_deps)}"
            elif not entry:
                is_dirty = True
                reason = "Missing cache entry"
            elif entry.fingerprint != fp:
                is_dirty = True
                reason = f"Fingerprint mismatch: cached={entry.fingerprint[:8]}... current={fp[:8]}..."
            elif entry.version != version:
                is_dirty = True
                reason = f"Version mismatch: cached={entry.version} current={version}"

            if is_dirty:
                dirty_nodes.add(name)
                reasons[name] = reason
                ordered_nodes.append(name)
            else:
                unchanged_nodes.append(name)

        metrics = RebuildMetrics(
            cache_hits=len(unchanged_nodes),
            cache_misses=len(ordered_nodes),
            dirty_count=len(dirty_nodes),
            scheduled_count=len(ordered_nodes)
        )

        return RebuildPlan(
            dirty_nodes=dirty_nodes,
            ordered_nodes=ordered_nodes,
            unchanged_nodes=unchanged_nodes,
            reasons=reasons,
            metrics=metrics,
            resolved_fingerprints=resolved_fingerprints
        )
