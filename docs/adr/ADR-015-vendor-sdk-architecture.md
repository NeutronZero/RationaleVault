# ADR-015: Vendor SDK Architecture

**Status**: Accepted
**Date**: 2026-06-26
**Deciders**: RationaleVault team
**Technical Story**: How do we support agent-specific integrations without coupling the platform to any vendor?

---

## Context

RationaleVault supports multiple AI agents (Claude, Codex, Cursor, OpenCode, Gemini). Each agent has:
- A unique API format (Claude's messages, Codex's CLI, Cursor's WebSocket)
- Unique capabilities (Claude has MCP, Codex has exec, etc.)
- Unique serialization needs (JSON, protobuf, custom formats)

The **Transport SDK** (v2.3) handles HOW data moves between agents and the platform. But it doesn't know WHAT each agent's data means.

## Decision

Introduce a **Vendor SDK** extension layer that sits between Transport SDK and Agent Implementations:

```
Agent Runtime
    ↕ AgentSession
Transport SDK (v2.3)
    ↕ TransportSession
Vendor SDK (v2.4)
    ↕ VendorAdapter
Agent Implementations
```

### Responsibilities

| Layer | Responsibility |
|-------|---------------|
| **Transport SDK** | Connection, negotiation, serialization pipeline |
| **Vendor SDK** | Capability mapping, vendor-native format, adapter interface |
| **Agent Implementations** | Concrete vendor adapters (ClaudeAdapter, etc.) |

### VendorAdapter Interface

Every vendor adapter implements:

```python
class VendorAdapter(ABC):
    def manifest(self) -> VendorManifest: ...
    def capability_mapping(self) -> CapabilityMapping: ...
    def serialize(self, package_dict: dict) -> bytes: ...
    def content_type(self) -> str: ...
    def format_name(self) -> str: ...
    def supported_transports(self) -> list[TransportType]: ...
    def is_compatible(self, transport_type: TransportType) -> bool: ...
```

### VendorManifest (VMNF-[hash])

```python
@dataclass(frozen=True)
class VendorManifest:
    manifest_id: str            # VMNF-[hash]
    name: str
    vendor_id: str              # "anthropic", "openai"
    version: str
    supported_transports: list[TransportType]
    supported_capabilities: frozenset[Capability]
    default_serializer: str
    status: VendorStatus        # ACTIVE | DEPRECATED | EXPERIMENTAL
    metadata: dict[str, str]
```

### CapabilityMapping

Bidirectional mapping between vendor-specific and runtime capabilities:

```python
vendor_to_runtime["read"] = Capability.READ_WORKSPACE
runtime_to_vendor(Capability.READ_WORKSPACE) = "read"
```

Reverse map is auto-built from forward map. Immutable after construction.

### Design Rules

1. **Vendor SDK is extension, not platform.** Vendor adapters are contributed, not core.
2. **Transport stays generic.** Transport adapters don't know about vendors.
3. **Capability mapping is deterministic.** Same vendor → same mapping.
4. **Serialization is a transport concern.** Vendors select the serializer, transport executes it.

## Consequences

### Positive
- Clean separation of concerns (Transport vs Vendor)
- New vendors added as extensions without changing transport layer
- Vendors can be deprecated independently
- Testing: mock VendorAdapter easily

### Negative
- One more abstraction layer (minimal overhead)
- Vendor adapters must implement the full interface

## Alternatives Considered

### 1. Extend TransportAdapter to include vendor logic
**Rejected**: Conflates HOW data moves with WHAT data means. Transport adapters would need to know about every vendor.

### 2. Monolithic vendor connector (one class per vendor)
**Rejected**: Duplicates connection/serialization logic. No shared transport infrastructure.

### 3. Configuration-driven vendor adapters
**Rejected**: Too rigid for complex vendor-specific logic (Claude's MCP is fundamentally different from Codex's CLI).

## Relationships

- Extends: ADR-014 (Transport/Vendor Separation)
- Implements: H2 (Vendor SDK)
- Frozen: v2.4 (Vendor SDK Freeze)

---

*ADR-015 — Accepted 2026-06-26*
