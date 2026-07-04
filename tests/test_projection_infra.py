from __future__ import annotations
import pytest
from typing import ClassVar
from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.projections.registry import (
    ProjectionRegistry,
    CircularDependencyError,
    MissingDependencyError,
    DuplicateProjectionError,
    InvalidDependencyKindError,
)
from rationalevault.projections.bootstrap import build_default_registry

def test_semver_parsing_and_comparison():
    v1 = SemVer.parse("1.0.0")
    v2 = SemVer.parse("1.1.0")
    v3 = SemVer.parse("1.1.1")
    v4 = SemVer(2, 0, 0)

    assert v1 < v2
    assert v2 < v3
    assert v3 < v4
    assert str(v1) == "1.0.0"

    with pytest.raises(ValueError):
        SemVer.parse("invalid")
    with pytest.raises(ValueError):
        SemVer.parse("1.0")
    with pytest.raises(ValueError):
        SemVer.parse("1.0.a")

def test_default_registry_bootstraps_successfully():
    registry = build_default_registry()
    projs = registry.get_all()
    assert len(projs) == 12
    assert "Alias" in projs
    assert "BM25" in projs
    assert "Session" in projs
    assert "Continuation" in projs
    assert "Knowledge" in projs
    assert "Knowledge Graph" in projs
    
    order = registry.topological_sort()
    assert len(order) == 12

def test_duplicate_registration_failures():
    class TestProj(BaseProjection):
        projection_name: ClassVar[str] = "Test"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []

    registry = ProjectionRegistry()
    registry.register(TestProj)

    # Registering the same class twice fails
    with pytest.raises(DuplicateProjectionError):
        registry.register(TestProj)

    # Registering a different class with same projection_name fails
    class TestProjCollision(BaseProjection):
        projection_name: ClassVar[str] = "Test"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []

    with pytest.raises(DuplicateProjectionError):
        registry.register(TestProjCollision)

def test_missing_dependency_failure():
    class DependentProj(BaseProjection):
        projection_name: ClassVar[str] = "Dependent"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.COMPOSITE
        
        # Depends on unregistered projection
        dependencies: ClassVar[list[type[BaseProjection]]] = []

    # Let's dynamically inject a class reference not in registry
    class MissingProj(BaseProjection):
        projection_name: ClassVar[str] = "Missing"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []

    DependentProj.dependencies = [MissingProj]

    registry = ProjectionRegistry()
    registry.register(DependentProj)

    with pytest.raises(MissingDependencyError):
        registry.validate()

def test_kind_violations():
    # 1. BASE projection must not have dependencies
    class BaseDep(BaseProjection):
        projection_name: ClassVar[str] = "BaseDep"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []

    class BaseWithDep(BaseProjection):
        projection_name: ClassVar[str] = "BaseWithDep"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = [BaseDep]

    registry1 = ProjectionRegistry()
    registry1.register(BaseDep)
    registry1.register(BaseWithDep)
    with pytest.raises(InvalidDependencyKindError):
        registry1.validate()

    # 2. DERIVED projection cannot depend on COMPOSITE
    class CompositeDep(BaseProjection):
        projection_name: ClassVar[str] = "CompositeDep"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.COMPOSITE
        dependencies: ClassVar[list[type[BaseProjection]]] = []

    class DerivedWithCompositeDep(BaseProjection):
        projection_name: ClassVar[str] = "DerivedWithCompositeDep"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
        dependencies: ClassVar[list[type[BaseProjection]]] = [CompositeDep]

    registry2 = ProjectionRegistry()
    registry2.register(CompositeDep)
    registry2.register(DerivedWithCompositeDep)
    with pytest.raises(InvalidDependencyKindError):
        registry2.validate()

def test_circular_dependency_failure():
    class CyclicA(BaseProjection):
        projection_name: ClassVar[str] = "CyclicA"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.COMPOSITE
        dependencies: ClassVar[list[type[BaseProjection]]] = []

    class CyclicB(BaseProjection):
        projection_name: ClassVar[str] = "CyclicB"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.COMPOSITE
        dependencies: ClassVar[list[type[BaseProjection]]] = [CyclicA]

    CyclicA.dependencies = [CyclicB]

    registry = ProjectionRegistry()
    registry.register(CyclicA)
    registry.register(CyclicB)

    with pytest.raises(CircularDependencyError):
        registry.validate()

def test_deterministic_and_order_independent_sorting():
    class NodeA(BaseProjection):
        projection_name: ClassVar[str] = "NodeA"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []
        build_priority: ClassVar[int] = 100

    class NodeB(BaseProjection):
        projection_name: ClassVar[str] = "NodeB"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []
        build_priority: ClassVar[int] = 50

    class NodeC(BaseProjection):
        projection_name: ClassVar[str] = "NodeC"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []
        build_priority: ClassVar[int] = 100

    # Registration order: A, B, C
    registry1 = ProjectionRegistry()
    registry1.register(NodeA)
    registry1.register(NodeB)
    registry1.register(NodeC)
    order1 = registry1.topological_sort()

    # Registration order: C, B, A
    registry2 = ProjectionRegistry()
    registry2.register(NodeC)
    registry2.register(NodeB)
    registry2.register(NodeA)
    order2 = registry2.topological_sort()

    # The resulting sort order should be identical and deterministic:
    # NodeB (priority 50) -> NodeA (priority 100, alphabetical first) -> NodeC (priority 100, alphabetical second)
    expected_order = [NodeB, NodeA, NodeC]
    assert order1 == expected_order
    assert order2 == expected_order

def test_lookup_apis():
    class LookupProj(BaseProjection):
        projection_name: ClassVar[str] = "Lookup"
        version: ClassVar[SemVer] = SemVer(1, 0, 0)
        projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
        dependencies: ClassVar[list[type[BaseProjection]]] = []

    registry = ProjectionRegistry()
    registry.register(LookupProj)

    assert registry.get_projection("Lookup") == LookupProj
    assert registry.get_projection(LookupProj) == LookupProj

    with pytest.raises(KeyError):
        registry.get_projection("Missing")
