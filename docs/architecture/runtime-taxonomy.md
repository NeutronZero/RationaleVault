# Architecture Decision: Runtime Taxonomy

As part of Phase 3, we investigated the `Runtime` pattern across the codebase to identify actual structural duplication and evaluate if a unified `RuntimeManager` or `RuntimeRegistry` is justified.

## Methodology
We analyzed the six existing classes suffixed with `Runtime` across the codebase:
1. `GovernanceRuntime`
2. `MCPRuntime`
3. `RecommendationRuntime`
4. `AgentRuntime`
5. `SkillRuntime`
6. `TransportRuntime`

## Findings
The term "Runtime" in RationaleVault is currently used as a catch-all suffix for "the stateless service layer that operates on top of Projections and Events".

However, structurally, they fall into three distinct bounded contexts that share almost no common interfaces:

### Group A: Lifecycle Orchestrators
- **`AgentRuntime`**: `attach`, `detach`, `pause`, `resume`, `stream_package`
- **`TransportRuntime`**: `register`, `attach`, `detach`, `stream_package`
*Observation: These manage stateful sessions via pure functions. There is structural alignment between these two, but only two.*

### Group B: Execution Engines
- **`MCPRuntime`**: `execute_tool`, `build_manifest`
- **`SkillRuntime`**: `execute`
*Observation: These are sandboxed execution wrappers.*

### Group C: Query / Data Pipelines
- **`GovernanceRuntime`**: `evaluate_rules`, `search`
- **`RecommendationRuntime`**: `filter`, `enrich`, `rank`, `search`
*Observation: These are essentially domain-specific query builders operating on Materialized Projections.*

## Conclusion & Architecture Decision

**Shared naming does not imply shared abstraction.**

We will **NOT** introduce a `RuntimeManager`, `RuntimeRegistry`, or a common `Runtime` interface. 
There is no justification for a unified interface, as forcing one would result in a bloated, non-cohesive God Object (e.g., a manager that forces `execute`, `search`, and `attach` onto classes that only need one of them).

The current modular approach—where each domain exposes its own stateless service layer—is correct. The only recommendation is a future stylistic one: renaming `GovernanceRuntime` to `GovernanceService` or `GovernanceQueries` to avoid the overloaded "Runtime" nomenclature, though this is not urgent.
