"""
RationaleVault MCP Server v2 Runtime — Workspace-backed tool execution.

The MCPToolRegistry manages tool definitions and bindings.
The MCPRuntime orchestrates tool execution through WorkspaceContext.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from rationalevault.mcp.v2_models import (
    MCPBinding,
    MCPManifest,
    MCPToolCategory,
    MCPToolDef,
    MCPToolResult,
    MCPSessionMode,
)
from rationalevault.workspace.models import WorkspaceContext


# =====================================================================
# Tool Registry
# =====================================================================

@dataclass
class MCPToolRegistry:
    """
    Immutable registry of MCP tool definitions and bindings.

    Tools are registered at startup; bindings are created per-workspace.
    """
    _tools: dict[str, MCPToolDef] = field(default_factory=dict)
    _bindings: dict[str, MCPBinding] = field(default_factory=dict)
    _handlers: dict[str, Callable] = field(default_factory=dict)

    def register_tool(
        self,
        name: str,
        description: str,
        category: MCPToolCategory,
        handler: Callable,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        required_capabilities: frozenset[str] | None = None,
        session_mode: MCPSessionMode = MCPSessionMode.STATELESS,
    ) -> MCPToolDef:
        """Register a tool definition and its handler."""
        tool_id = MCPToolDef.generate_tool_id(name, category.value)
        tool = MCPToolDef(
            tool_id=tool_id,
            name=name,
            description=description,
            category=category,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
            required_capabilities=required_capabilities or frozenset(),
            session_mode=session_mode,
        )
        self._tools[tool_id] = tool
        self._handlers[tool_id] = handler
        return tool

    def get_tool(self, tool_id: str) -> MCPToolDef | None:
        return self._tools.get(tool_id)

    def get_handler(self, tool_id: str) -> Callable | None:
        return self._handlers.get(tool_id)

    def get_tool_by_name(self, name: str) -> MCPToolDef | None:
        for tool in self._tools.values():
            if tool.name == name:
                return tool
        return None

    def list_tools(self, category: MCPToolCategory | None = None) -> list[MCPToolDef]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def create_binding(
        self,
        tool_id: str,
        workspace_id: str,
        agent_session_id: str | None = None,
        vendor_id: str | None = None,
    ) -> MCPBinding:
        """Create a binding between a tool and a workspace."""
        binding_id = MCPBinding.generate_binding_id(tool_id, workspace_id)
        binding = MCPBinding(
            binding_id=binding_id,
            tool_id=tool_id,
            workspace_id=workspace_id,
            agent_session_id=agent_session_id,
            vendor_id=vendor_id,
        )
        self._bindings[binding_id] = binding
        return binding

    def get_binding(self, binding_id: str) -> MCPBinding | None:
        return self._bindings.get(binding_id)

    def get_bindings_for_workspace(self, workspace_id: str) -> list[MCPBinding]:
        return [b for b in self._bindings.values() if b.workspace_id == workspace_id]

    def tool_count(self) -> int:
        return len(self._tools)

    def binding_count(self) -> int:
        return len(self._bindings)


# =====================================================================
# MCP Runtime
# =====================================================================

@dataclass
class MCPRuntime:
    """
    Orchestrates MCP tool execution through WorkspaceContext.

    Every tool invocation:
      1. Looks up the tool definition
      2. Validates the binding
      3. Compiles WorkspaceContext
      4. Executes the handler
      5. Returns MCPToolResult
    """
    registry: MCPToolRegistry = field(default_factory=MCPToolRegistry)

    def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        workspace_context: WorkspaceContext | None = None,
    ) -> MCPToolResult:
        """Execute a tool by name with the given arguments."""
        tool = self.registry.get_tool_by_name(tool_name)
        if not tool:
            return MCPToolResult(
                tool_id="UNKNOWN",
                success=False,
                error=f"Tool '{tool_name}' not found",
            )

        handler = self.registry.get_handler(tool.tool_id)
        if not handler:
            return MCPToolResult(
                tool_id=tool.tool_id,
                success=False,
                error=f"No handler registered for tool '{tool_name}'",
            )

        try:
            result_data = handler(arguments, workspace_context)
            context_hash = None
            if workspace_context:
                context_hash = hashlib.sha256(
                    str(workspace_context.to_dict()).encode("utf-8"),
                ).hexdigest()[:16]

            return MCPToolResult(
                tool_id=tool.tool_id,
                success=True,
                data=result_data,
                context_hash=context_hash,
            )
        except Exception as e:
            return MCPToolResult(
                tool_id=tool.tool_id,
                success=False,
                error=str(e),
            )

    def execute_tool_with_binding(
        self,
        binding_id: str,
        arguments: dict[str, Any],
        workspace_context: WorkspaceContext | None = None,
    ) -> MCPToolResult:
        """Execute a tool through a specific binding."""
        binding = self.registry.get_binding(binding_id)
        if not binding:
            return MCPToolResult(
                tool_id="UNKNOWN",
                success=False,
                error=f"Binding '{binding_id}' not found",
            )

        tool = self.registry.get_tool(binding.tool_id)
        if not tool:
            return MCPToolResult(
                tool_id=binding.tool_id,
                success=False,
                error=f"Tool '{binding.tool_id}' not found in binding",
            )

        return self.execute_tool(tool.name, arguments, workspace_context)

    def build_manifest(
        self,
        server_name: str = "rationalevault",
        version: str = "2.0.0",
    ) -> MCPManifest:
        """Build the server manifest from registered tools."""
        manifest_id = MCPManifest.generate_manifest_id(server_name, version)
        tools = self.registry.list_tools()
        return MCPManifest(
            manifest_id=manifest_id,
            server_name=server_name,
            version=version,
            tools=tools,
        )


# Need hashlib for context_hash
import hashlib
