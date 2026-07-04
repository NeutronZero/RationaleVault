# ADR-016: MCP Server v2 Architecture

**Status**: Accepted
**Date**: 2026-06-26
**Deciders**: RationaleVault team
**Technical Story**: How should the MCP server evolve to leverage the Workspace and Agent Runtime layers?

---

## Context

The original MCP server (v1) called raw projections directly. Each tool independently instantiated projections, compiled context, and returned raw data. This led to:

1. **Redundant projection reconstruction** — Organization tools independently rebuilt the full projection stack.
2. **No session management** — Every tool call was stateless; no concept of an ongoing agent session.
3. **No capability checks** — Tools didn't verify that the calling agent had the required capabilities.
4. **Inconsistent return types** — Some tools returned dicts, others returned strings or lists.

With the Workspace (v2.1), Agent Runtime (v2.2), Transport SDK (v2.3), and Vendor SDK (v2.4) now frozen, the MCP server should route through these layers instead of bypassing them.

## Decision

Rebuild the MCP server as **MCP Server v2**, routing through WorkspaceContext and AgentSession.

### Architecture

```
MCP Client
    ↕ MCP Protocol
MCP Server v2
    ↕ MCPToolRegistry + MCPRuntime
Workspace Layer
    ↕ WorkspaceContext
Agent Runtime
    ↕ AgentSession + Capabilities
```

### Key Design Decisions

**1. WorkspaceContext as the universal input**

Every MCP tool receives a `WorkspaceContext` (or `None` for stateless tools). The context carries:
- Workspace state (goals, decisions, executions)
- Agent roster
- Continuation state
- Memory focus
- Lineage summary

This eliminates redundant projection reconstruction — the context is compiled once per request.

**2. MCPToolRegistry with bindings**

Tools are registered once at startup. Bindings connect tools to specific workspaces and optional agent sessions. This enables:
- Per-workspace tool configuration
- Agent-specific tool access
- Vendor-specific tool formatting

**3. Standardized MCPToolResult**

Every tool returns an `MCPToolResult`, not raw data. This ensures:
- Consistent error handling
- Context hash for audit trails
- WorkspacePackage references for streaming

**4. Session modes**

Tools declare their session mode:
- `STATELESS` — Fresh context each call (most tools)
- `SESSION` — Persistent session across calls (continuation, multi-step workflows)
- `STREAMING` — Long-lived streaming sessions (real-time updates)

**5. Capability-gated tools**

Tools declare required capabilities. The runtime verifies agent capabilities before execution.

### Tool Categories

| Category | Purpose | Example |
|----------|---------|---------|
| READ | Read-only queries | `get_context`, `search_memories` |
| WRITE | State mutations | `record_event` |
| STREAM | Long-lived streams | `watch_workspace` |
| ADMIN | Server management | `get_manifest` |

## Consequences

### Positive
- Eliminates redundant projection reconstruction
- Enables session-aware tool execution
- Provides capability-gated access control
- Standardized error handling across all tools
- Clean separation between tool definitions and implementations

### Negative
- One more abstraction layer (minimal overhead)
- Tools must accept WorkspaceContext parameter

## Alternatives Considered

### 1. Keep v1 architecture (direct projection calls)
**Rejected**: Redundant computation, no session management, no capability checks.

### 2. Build a custom protocol layer
**Rejected**: MCP is an emerging standard; building custom would fragment the ecosystem.

## Relationships

- Depends on: ADR-011 (Workspace), ADR-013 (Agent Runtime), ADR-014 (Transport/Vendor)
- Implements: H3 (MCP Server v2)
- Frozen: v2.5 (MCP Server v2 Freeze)

---

*ADR-016 — Accepted 2026-06-26*
