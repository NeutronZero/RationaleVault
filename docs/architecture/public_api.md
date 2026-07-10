# RationaleVault Public API & Compatibility

As RationaleVault evolves from a foundational project into a robust developer platform, we maintain strict boundaries between public extension points and internal architecture.

## API Tiers

RationaleVault classifies its APIs into three tiers:

### 1. Stable Public API
These are the core extension points and data contracts developers rely on.
**Compatibility Guarantee:** No breaking changes except on major version releases (e.g., 2.x.x -> 3.0.0).

### 2. Advanced API
These are interfaces meant for power users (e.g., orchestrating custom runtimes or manually managing dependencies).
**Compatibility Guarantee:** Can evolve in minor releases, but any breaking changes must be preceded by a formal deprecation period (at least one minor release cycle) emitting `DeprecationWarning`.

### 3. Internal
All other modules (compilers, replay engines, snapshot internals, registries, CLI tools).
**Compatibility Guarantee:** None. These may be heavily refactored or removed at any time without warning. Developers MUST NOT import from internal modules.

## Deprecation Policy

When a **Stable** or **Advanced** API is scheduled for removal or significant alteration:
1. **Deprecation:** A `DeprecationWarning` is added to the implementation. The symbol is marked as deprecated in documentation.
2. **Grace Period:** The API remains fully functional for at least one major cycle (for Stable) or one minor cycle (for Advanced).
3. **Removal:** The API is removed in the subsequent major/minor release.

## Symbol Table

The following table explicitly defines the tier for primary RationaleVault symbols. All these symbols should be imported from their respective package roots (e.g., `from rationalevault.projection_platform import Projection`).

| Symbol | Package Route | Status | Compatibility |
|--------|--------------|--------|---------------|
| `Projection` | `rationalevault.projection_platform` | Stable | Major-only changes |
| `ProjectionContext` | `rationalevault.projection_platform` | Stable | Major-only changes |
| `ProjectionConformanceProvider` | `rationalevault.projection_platform` | Stable | Major-only changes |
| `ConformanceSuite` | `rationalevault.projection_platform` | Stable | Major-only changes |
| `ProjectionManager` | `rationalevault.projection_platform` | Advanced | Deprecation required |
| `DependencyReader` | `rationalevault.projection_platform` | Advanced | Deprecation required |
| `MetricsCollector` | `rationalevault.projection_platform` | Advanced | Deprecation required |
| `ProjectionCompiler` | `rationalevault.projection_platform` | Internal | No guarantees |
| `ReplayEngine` | `rationalevault.cognitive_head` | Internal | No guarantees |
| `EventRecord` | `rationalevault.schema` | Stable | Major-only changes |
| `EventType` | `rationalevault.schema` | Stable | Major-only changes |
| `EventMetadata` | `rationalevault.schema` | Stable | Major-only changes |
| `SchemaPolicy` | `rationalevault.schema` | Stable | Major-only changes |
| `BaseSkill` | `rationalevault.skills` | Stable | Major-only changes |
| `SkillManifest` | `rationalevault.skills` | Stable | Major-only changes |
| `SkillInput` | `rationalevault.skills` | Stable | Major-only changes |
| `MemoryProvider` | `rationalevault.memory` | Stable | Major-only changes |

## Best Practices
- **Use Package Root Imports:** Always prefer `from rationalevault.projection_platform import Projection` over deep imports like `from rationalevault.projection_platform.protocols import Projection`. Deep imports are considered implementation details and may break.
- **Do not bypass Platform Boundaries:** If you are building a custom CLI or MCP tool, you must interface through `ProjectionManager` or `SkillRuntime`, never directly importing `ProjectionCompiler` or `ReplayEngine`.
