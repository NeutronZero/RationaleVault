# Architecture Cookbook

Extending RationaleVault should feel predictable. This cookbook outlines the standard lifecycle for adding a new capability to the system.

Follow these steps in order when building a new feature.

---

## 1. Defining the Capability
Before writing code, define exactly what capability you are adding. 
* Is the agent learning a new skill?
* Are we extracting new insights from existing data?
* Are we building a new UI?

Write a short paragraph defining the capability. This helps constrain the feature scope.

## 2. Choosing an Extension Point
Use the [Choosing Abstractions Guide](choosing-abstractions.md) to determine the correct structural boundary for your feature. 
If your capability requires tracking historical state over time, you will need a **Projection**.

## 3. Defining Events
If you are building a Projection, you must define the facts it consumes.
1. Add your new event definitions to the `rationalevault/schema/` directory.
2. Events must be immutable dataclasses.
3. Event payloads should contain all the data needed to apply the event without requiring external lookups.

## 4. Building the Projection
If your feature requires a Projection:
1. Review the [Projection Checklist](projection-checklist.md).
2. Create `state.py` for your deterministic state dataclass.
3. Create `projection.py` for your reducer logic.
4. Remember: **Reducers never perform I/O**.

## 5. Writing the Runtime (If Needed)
Projections hold state, but they do not answer complex runtime queries (like searching, ranking, or filtering based on active user context).
1. Create a `runtime.py` in your domain module.
2. The Runtime should accept a reference to the Projection and the query parameters.
3. Runtimes must never mutate the projection state directly.

## 6. Adding CLI and MCP Adapters
Once your Runtime or Skill is complete, expose it to users.
1. Add a CLI command in `rationalevault/cli/commands/` using `click`.
2. Add an MCP Tool in `rationalevault/mcp/tools.py`.
3. **Crucial:** Your adapters must contain absolutely no business logic. They should merely parse arguments and call your Runtime/Skill.

## 7. Writing Conformance Tests
Test your implementation using the provided Conformance Suite.
1. Create `tests/unit/conformance/test_my_projection.py`.
2. Use the platform conformance fixtures to verify that your projection obeys the laws of determinism, idempotency, and snapshot restoration.

## 8. Adding Benchmarks
Performance regressions in reducers compound exponentially as the event log grows.
1. Add a benchmark in the `benchmarks/` directory at the project root.
2. Ensure your reducer can process at least 1,000 events per second.

## 9. Documenting the Feature
Finally, update the documentation. 
If your feature introduces a brand-new architectural pattern, add it to `docs/architecture/`. If it simply uses existing patterns, document its usage in the user-facing `README.md`.
