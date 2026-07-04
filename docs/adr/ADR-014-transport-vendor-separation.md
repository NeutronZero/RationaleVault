# ADR-014: Transport/Vendor Separation

**Date:** 2026-06-26
**Status:** Accepted
**Supersedes:** N/A

## Context

External agents (Claude, Codex, Cursor, OpenCode, Gemini) need to interact with RationaleVault. Without explicit separation, connectors mix transport concerns (MCP, REST, CLI, WebSocket) with vendor concerns (Anthropic, OpenAI, Google), creating an N×M coupling problem.

## Decision

Formalize a four-layer architecture with transport and vendor as separate, independently freezable layers.

### Architecture

```
Agent Runtime (v2.2)
        │
        ▼
Transport SDK (H1) — platform layer, frozen
  ├── TransportManifest
  ├── TransportCapabilities
  ├── TransportSession
  ├── TransportNegotiation
  ├── BaseTransportAdapter (ABC)
  ├── WorkspacePackageSerializer
  └── Transport Events
        │
        ▼
Vendor SDK (H2) — extension layer
  ├── VendorManifest
  ├── VendorAdapter
  ├── Capability Mapping
  ├── Serialization Mapping
  └── Thin Connector
        │
        ▼
Agent Implementations
  ├── Claude (MCP transport)
  ├── Codex (CLI, REST transport)
  ├── Cursor (WebSocket transport)
  ├── OpenCode (MCP, CLI transport)
  └── Gemini (REST transport)
```

### Separation Principle

**Transports** define HOW data moves between runtime and agents:
- MCP (Model Context Protocol)
- REST (HTTP)
- WebSocket
- CLI (stdin/stdout)
- IPC (inter-process communication)
- Filesystem (future)
- gRPC (future)

**Vendors** define WHAT data means to a specific agent:
- Capability mapping (vendor-specific capabilities → runtime capabilities)
- Serialization mapping (WorkspacePackage → vendor-native format)
- Transport selection (which transports the vendor supports)

### Why Separate

1. **Stability:** Transports change rarely. Vendors change frequently.
2. **Testability:** Transport tests are independent of vendor tests.
3. **Composability:** Multiple vendors can share the same transport.
4. **Extensibility:** New transports don't require new vendor code, and vice versa.

### Serialization Boundary

Every vendor speaks a different dialect. The `WorkspacePackageSerializer` converts `WorkspacePackage` into vendor-native format:

```
WorkspacePackage
      ↓
Serializer
      ↓
Claude Messages Format
```

```
WorkspacePackage
      ↓
Serializer
      ↓
Codex CLI Prompt
```

The serializer is a transport-level concern, not a vendor concern.

### Capability Negotiation

Instead of hardcoding transport assumptions, `TransportCapabilities` advertises what a transport supports:

- `supports_streaming`
- `supports_bidirectional`
- `supports_binary`
- `supports_incremental_updates`
- `supports_resume`
- `supports_tool_calls`
- `supports_large_context`

The runtime negotiates against capabilities, not protocol names.

## Rationale

- **Platform/Extension pattern:** Transport SDK is a platform layer (frozen contracts). Vendor SDK is an extension layer (vendor-specific behavior through stable interfaces).
- **Reduced test matrix:** Instead of `Vendor × Transport × Runtime`, test `Transport + Vendor Mapping + Integration`.
- **Future-proof:** New transports (gRPC, filesystem) and new vendors (future AI systems) integrate without modifying existing layers.

## Consequences

- H1 freezes the Transport SDK contracts before any vendor implementation.
- H2 becomes nearly declarative: manifest + capability mapping + serialization mapping.
- The runtime rejects incompatible transports at negotiation time, not at runtime.
- All existing patterns (event sourcing, deterministic projections, frozen dataclasses) apply to the transport layer.

## Related Documents

- `docs/v2.2_agent_runtime_freeze.md` — Agent Runtime (upstream)
- `docs/adr/ADR-013-agent-runtime-architecture.md` — Agent Runtime ADR
