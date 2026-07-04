# ADR-013: Agent Runtime Architecture

**Date:** 2026-06-26
**Status:** Accepted
**Supersedes:** N/A

## Context

External agents (Claude, Codex, Cursor, OpenCode, Gemini) need to interact with RationaleVault workspaces. Without a runtime layer, each connector would independently implement:
- Session management
- Capability negotiation
- Workspace binding
- Context package streaming
- Protocol versioning

This creates duplication and inconsistency across connectors.

## Decision

Introduce an Agent Runtime as the platform layer between Workspace and external agents.

### Architecture

```
Workspace Layer
      ↓
Agent Runtime
  ├── SessionRegistry
  ├── CapabilityResolver
  ├── WorkspaceBinder
  ├── PackageStreamer
  └── AgentRuntime (orchestrator)
      ↓
Connector SDK
      ↓
Claude | Codex | Cursor | OpenCode | Gemini
```

### Key Design Choices

1. **AgentProfile ≠ AgentSession:** Identity (WHO) is separate from running state (WHAT). Multiple concurrent sessions can share a profile.

2. **Composable Capabilities:** Rather than simple boolean permissions, capabilities are composable sets: `effective = granted - denied`. Predefined profiles (OBSERVER, PLANNER, RESEARCHER, EXECUTOR, ADMINISTRATOR) define common capability sets.

3. **Session Lifecycle:** Event-sourced from day one: `SESSION_CREATED → SESSION_ATTACHED → PACKAGE_STREAMED → SESSION_PAUSED → SESSION_RESUMED → SESSION_DETACHED → SESSION_CLOSED`.

4. **Protocol Versioning:** Major-version compatibility check ensures agents and runtime are compatible before establishing sessions.

5. **Pure Functions:** All runtime methods are deterministic, no I/O. Same design philosophy as Workspace Service.

## Rationale

- **Thin connectors:** Every connector becomes a thin adapter over the runtime.
- **Consistent behavior:** Session management, capabilities, and streaming work identically across all agents.
- **Extensible:** New agents integrate by implementing a thin connector, not rebuilding infrastructure.
- **Testable:** Pure functions enable deterministic testing without mocking.

## Consequences

- All agent integrations depend on the runtime contracts (L1 frozen).
- New connectors are thin adapters, not standalone implementations.
- The runtime becomes the API surface for agent ecosystem (H1-H5).
- Protocol versioning enables backward-compatible evolution.

## Related Documents

- `docs/v2.1_workspace_freeze.md` — Workspace architecture (upstream)
- `docs/adr/ADR-011-workspace-architecture.md` — Workspace ADR
- `docs/adr/ADR-012-promotion-pipeline-pattern.md` — Pipeline pattern
