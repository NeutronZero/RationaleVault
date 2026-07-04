from __future__ import annotations
from rationalevault.projections.registry import ProjectionRegistry

def build_default_registry() -> ProjectionRegistry:
    """Explicitly bootstraps the default ProjectionRegistry and validates all core projections."""
    from rationalevault.projections.alias import AliasProjection
    from rationalevault.projections.bm25 import BM25IndexProjection
    from rationalevault.projections.session import SessionProjection
    from rationalevault.projections.continuation import ContinuationProjection
    from rationalevault.projections.knowledge import KnowledgeProjection
    from rationalevault.projections.graph import GraphProjection
    from rationalevault.projections.cross_project import CrossProjectProjection
    from rationalevault.organization.projection import OrganizationProjection
    from rationalevault.organization.graph import OrganizationGraphProjection
    from rationalevault.organization.activity import OrganizationActivityProjection
    from rationalevault.organization.continuation import OrganizationContinuationProjection
    from rationalevault.projections.reflection import ReflectionStateProjection

    registry = ProjectionRegistry()
    registry.register(AliasProjection)
    registry.register(BM25IndexProjection)
    registry.register(SessionProjection)
    registry.register(ContinuationProjection)
    registry.register(KnowledgeProjection)
    registry.register(GraphProjection)
    registry.register(CrossProjectProjection)
    registry.register(OrganizationProjection)
    registry.register(OrganizationGraphProjection)
    registry.register(OrganizationActivityProjection)
    registry.register(OrganizationContinuationProjection)
    registry.register(ReflectionStateProjection)


    # Validate graph structure at bootstrap time
    registry.validate()
    return registry
