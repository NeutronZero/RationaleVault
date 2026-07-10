"""Projection Platform — unified abstraction for deterministic projections."""
from __future__ import annotations

from rationalevault.projection_platform.manager import ProjectionManager
from rationalevault.projection_platform.protocols import Projection
from rationalevault.projection_platform.context import ProjectionContext, DependencyReader, MetricsCollector
from rationalevault.projection_platform.models import (
    ProjectionCapabilities, 
    ProjectionHealth,
    ProjectionMetadata,
    EventSelector
)
from rationalevault.projection_platform.conformance.suite import ConformanceSuite
from rationalevault.projection_platform.conformance.providers import ProjectionConformanceProvider

__all__ = [
    "Projection",
    "ProjectionContext",
    "ProjectionManager",
    "DependencyReader",
    "MetricsCollector",
    "ProjectionCapabilities",
    "ProjectionHealth",
    "ProjectionMetadata",
    "EventSelector",
    "ConformanceSuite",
    "ProjectionConformanceProvider",
]
