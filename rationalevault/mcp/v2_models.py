"""
RationaleVault MCP Server v2 — Workspace-backed protocol layer.

MCP Server v2 routes through Workspace + Agent Runtime instead of raw projections.
Tools are backed by WorkspaceContext compilation and AgentSession management.

Design rules:
  - Every MCP tool operates through a WorkspaceContext.
  - Agent sessions are managed via AgentRuntime.
  - Tools produce WorkspacePackages, not raw projection data.
  - Transport serialization is handled by the Transport SDK.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any



# =====================================================================
# Enums
# =====================================================================

class MCPToolCategory(str, Enum):
    """Categories of MCP tools."""
    READ = "READ"
    WRITE = "WRITE"
    STREAM = "STREAM"
    ADMIN = "ADMIN"


class MCPSessionMode(str, Enum):
    """Session lifecycle modes."""
    STATELESS = "STATELESS"        # No session, fresh context each call
    SESSION = "SESSION"            # Persistent session across calls
    STREAMING = "STREAMING"        # Long-lived streaming session


# =====================================================================
# MCP Tool Definition
# =====================================================================

@dataclass(frozen=True)
class MCPToolDef:
    """
    Immutable definition of an MCP tool.

    MCPT-[hash] — deterministic tool identity.
    """
    tool_id: str                    # MCPT-[hash]
    name: str
    description: str
    category: MCPToolCategory
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    session_mode: MCPSessionMode = MCPSessionMode.STATELESS

    @staticmethod
    def generate_tool_id(name: str, category: str) -> str:
        data = f"mcp_tool:{name}:{category}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MCPT-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "required_capabilities": sorted(self.required_capabilities),
            "session_mode": self.session_mode.value,
        }


# =====================================================================
# MCP Binding
# =====================================================================

@dataclass(frozen=True)
class MCPBinding:
    """
    Binds an MCP tool to a workspace and optional agent session.

    MCPB-[hash] — immutable binding identifier.
    """
    binding_id: str                 # MCPB-[hash]
    tool_id: str
    workspace_id: str
    agent_session_id: str | None = None
    vendor_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_binding_id(tool_id: str, workspace_id: str) -> str:
        data = f"mcp_binding:{tool_id}:{workspace_id}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MCPB-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "tool_id": self.tool_id,
            "workspace_id": self.workspace_id,
            "agent_session_id": self.agent_session_id,
            "vendor_id": self.vendor_id,
            "metadata": self.metadata,
        }


# =====================================================================
# MCP Tool Result
# =====================================================================

@dataclass(frozen=True)
class MCPToolResult:
    """
    Standardized result from an MCP tool invocation.

    Every tool returns a ToolResult, not raw data.
    """
    tool_id: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    context_hash: str | None = None     # Hash of the WorkspaceContext used
    workspace_package_ref: str | None = None  # WSPKG reference if applicable

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "context_hash": self.context_hash,
            "workspace_package_ref": self.workspace_package_ref,
        }


# =====================================================================
# MCP Manifest
# =====================================================================

@dataclass(frozen=True)
class MCPManifest:
    """
    Describes the MCP server's capabilities.

    MCPM-[hash] — server identity.
    """
    manifest_id: str                # MCPM-[hash]
    server_name: str
    version: str
    tools: list[MCPToolDef] = field(default_factory=list)
    supported_transports: list[str] = field(default_factory=lambda: ["stdio", "sse"])
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def generate_manifest_id(server_name: str, version: str) -> str:
        data = f"mcp_manifest:{server_name}:{version}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MCPM-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "server_name": self.server_name,
            "version": self.version,
            "tools": [t.to_dict() for t in self.tools],
            "supported_transports": self.supported_transports,
            "metadata": self.metadata,
        }
