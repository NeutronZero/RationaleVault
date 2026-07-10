# RationaleVault Developer Guide

Welcome to the RationaleVault Developer Guide. This is your single entry point for understanding, extending, and building upon the RationaleVault platform. 

This guide is structured around the lifecycle of extending the system. Whether you are building your first projection, digging into the core architecture, or stabilizing a custom runtime, you'll find the canonical resources here.

---

## 1. Getting Started

- [Installation & Setup](README.md)
- [Architecture Overview](architecture/README.md)
- [Glossary of Terms](architecture/glossary.md)

## 2. Architecture

- [The Projection Platform](architecture/projection_platform.md)
- [The Cognitive Head](architecture/cognitive_head.md)
- [Architectural Decision Records (ADRs)](architecture/adr/README.md)

## 3. Public API

- [Public API & Compatibility Matrix](architecture/public_api.md)

## 4. Extension Points

RationaleVault is designed to be extended. The following guides cover the core extension points:

### Building a Projection
Projections materialize derived state from the event stream. They are pure, deterministic, and highly testable.
- [Projection Archetypes](architecture/cookbook.md#projection-archetypes)
- [Projection Conformance Testing](architecture/cookbook.md#conformance-testing)
- Reference Example: `examples/projection_example/`

### Building a Runtime
Runtimes provide execution environments (like MCP or CLI) that map external triggers to RationaleVault events.
- Reference Example: `examples/runtime_example/`

### Building a Skill
Skills are self-contained functional units that externalize complex AI tasks (e.g., search, extraction).
- Reference Example: `examples/skill_example/`

## 5. Conformance

Every extension must pass rigorous architectural and behavioral invariants.
- [Executable Projection Laws](architecture/cookbook.md#executable-projection-laws)
- [Architecture Guards](tests/unit/test_architecture_guards.py)

## 6. Generators

RationaleVault provides powerful example-driven generators to scaffold your extensions:

```bash
# Scaffold a new projection (creates ./my_projection)
rationalevault new projection my_projection --with-cli --with-mcp

# Scaffold a new skill
rationalevault new skill my_skill
```
Generators derive entirely from the canonical examples in the `examples/` directory and perform strict post-generation validation.

## 7. Testing

- Run the full suite: `pytest`
- Run architecture guards: `pytest tests/unit/test_architecture_guards.py`
- Run public API tests: `pytest tests/unit/test_api_compatibility.py tests/unit/test_public_api_smoke.py`

## 8. Release Compatibility

- RationaleVault adheres strictly to the API evolution guarantees defined in the [Compatibility Matrix](architecture/public_api.md).
- Automated CI snapshots ensure that Stable and Advanced APIs are never accidentally broken.
