"""
H3 — MCP Server v2 Tests.

MCPToolDef, MCPBinding, MCPToolResult, MCPManifest, MCPToolRegistry, MCPRuntime.
"""
from __future__ import annotations

import pytest
from typing import Any

from rationalevault.mcp.v2_models import (
    MCPBinding,
    MCPManifest,
    MCPToolCategory,
    MCPToolDef,
    MCPToolResult,
    MCPSessionMode,
)
from rationalevault.mcp.v2_runtime import MCPRuntime, MCPToolRegistry
from rationalevault.workspace.models import WorkspaceContext


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_tool_def(
    name: str = "get_context",
    category: MCPToolCategory = MCPToolCategory.READ,
) -> MCPToolDef:
    tool_id = MCPToolDef.generate_tool_id(name, category.value)
    return MCPToolDef(
        tool_id=tool_id,
        name=name,
        description=f"Tool: {name}",
        category=category,
        input_schema={"query": {"type": "string"}},
        output_schema={"data": {"type": "object"}},
    )


def _make_binding(tool_id: str = "MCPT-TEST", workspace_id: str = "WS-TEST") -> MCPBinding:
    binding_id = MCPBinding.generate_binding_id(tool_id, workspace_id)
    return MCPBinding(
        binding_id=binding_id,
        tool_id=tool_id,
        workspace_id=workspace_id,
    )


def _make_workspace_context() -> WorkspaceContext:
    return WorkspaceContext(
        context_id="CTX-TEST",
        session_id="WSSSN-TEST",
        snapshot_id="WSSNP-TEST",
        agent_id="AGNT-TEST",
        goals=[],
        open_decisions=[],
        running_executions=[],
        pending_reflections=[],
        recent_knowledge=[],
        planner_policy_summary="default",
        memory_focus=[],
        lineage_summary=[],
        created_at="2026-06-26T12:00:00Z",
    )


# ── MCPToolDef ────────────────────────────────────────────────────────────

class TestMCPToolDef:
    def test_frozen(self):
        t = _make_tool_def()
        with pytest.raises(AttributeError):
            t.name = "hacked"

    def test_to_dict(self):
        t = _make_tool_def()
        d = t.to_dict()
        assert d["name"] == "get_context"
        assert d["category"] == "READ"
        assert "input_schema" in d
        assert "output_schema" in d

    def test_generate_id_deterministic(self):
        id1 = MCPToolDef.generate_tool_id("get_context", "READ")
        id2 = MCPToolDef.generate_tool_id("get_context", "READ")
        assert id1 == id2
        assert id1.startswith("MCPT-")

    def test_different_tools_different_ids(self):
        id1 = MCPToolDef.generate_tool_id("tool_a", "READ")
        id2 = MCPToolDef.generate_tool_id("tool_b", "READ")
        assert id1 != id2

    def test_session_mode_default(self):
        t = _make_tool_def()
        assert t.session_mode == MCPSessionMode.STATELESS

    def test_capabilities_in_dict(self):
        t = MCPToolDef(
            tool_id="MCPT-TEST",
            name="test",
            description="test",
            category=MCPToolCategory.READ,
            required_capabilities=frozenset({"read:workspace", "read:memory"}),
        )
        d = t.to_dict()
        assert "read:workspace" in d["required_capabilities"]
        assert "read:memory" in d["required_capabilities"]


# ── MCPBinding ────────────────────────────────────────────────────────────

class TestMCPBinding:
    def test_frozen(self):
        b = _make_binding()
        with pytest.raises(AttributeError):
            b.workspace_id = "hacked"

    def test_to_dict(self):
        b = _make_binding()
        d = b.to_dict()
        assert d["tool_id"] == "MCPT-TEST"
        assert d["workspace_id"] == "WS-TEST"
        assert d["binding_id"].startswith("MCPB-")

    def test_generate_id_deterministic(self):
        id1 = MCPBinding.generate_binding_id("MCPT-1", "WS-1")
        id2 = MCPBinding.generate_binding_id("MCPT-1", "WS-1")
        assert id1 == id2

    def test_different_bindings_different_ids(self):
        id1 = MCPBinding.generate_binding_id("MCPT-1", "WS-1")
        id2 = MCPBinding.generate_binding_id("MCPT-1", "WS-2")
        assert id1 != id2


# ── MCPToolResult ─────────────────────────────────────────────────────────

class TestMCPToolResult:
    def test_frozen(self):
        r = MCPToolResult(tool_id="MCPT-1", success=True, data={"x": 1})
        with pytest.raises(AttributeError):
            r.success = False

    def test_to_dict_success(self):
        r = MCPToolResult(
            tool_id="MCPT-1",
            success=True,
            data={"result": "ok"},
            context_hash="abc123",
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["data"]["result"] == "ok"
        assert d["context_hash"] == "abc123"
        assert d["error"] is None

    def test_to_dict_error(self):
        r = MCPToolResult(
            tool_id="MCPT-1",
            success=False,
            error="something failed",
        )
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"] == "something failed"

    def test_with_package_ref(self):
        r = MCPToolResult(
            tool_id="MCPT-1",
            success=True,
            data={},
            workspace_package_ref="WSPKG-abc",
        )
        d = r.to_dict()
        assert d["workspace_package_ref"] == "WSPKG-abc"


# ── MCPManifest ───────────────────────────────────────────────────────────

class TestMCPManifest:
    def test_frozen(self):
        m = MCPManifest(
            manifest_id="MCPM-1",
            server_name="test",
            version="1.0.0",
        )
        with pytest.raises(AttributeError):
            m.server_name = "hacked"

    def test_to_dict(self):
        tools = [_make_tool_def("t1"), _make_tool_def("t2")]
        m = MCPManifest(
            manifest_id="MCPM-1",
            server_name="rationalevault",
            version="2.0.0",
            tools=tools,
        )
        d = m.to_dict()
        assert d["server_name"] == "rationalevault"
        assert len(d["tools"]) == 2
        assert "stdio" in d["supported_transports"]

    def test_generate_id_deterministic(self):
        id1 = MCPManifest.generate_manifest_id("rv", "1.0")
        id2 = MCPManifest.generate_manifest_id("rv", "1.0")
        assert id1 == id2
        assert id1.startswith("MCPM-")

    def test_different_manifests_different_ids(self):
        id1 = MCPManifest.generate_manifest_id("rv", "1.0")
        id2 = MCPManifest.generate_manifest_id("rv", "2.0")
        assert id1 != id2


# ── MCPToolRegistry ───────────────────────────────────────────────────────

class TestMCPToolRegistry:
    def test_register_tool(self):
        reg = MCPToolRegistry()
        tool = reg.register_tool(
            name="get_context",
            description="Get context",
            category=MCPToolCategory.READ,
            handler=lambda args, ctx: {"data": "test"},
        )
        assert tool.name == "get_context"
        assert reg.tool_count() == 1

    def test_get_tool_by_name(self):
        reg = MCPToolRegistry()
        reg.register_tool(
            name="search_memories",
            description="Search",
            category=MCPToolCategory.READ,
            handler=lambda args, ctx: [],
        )
        tool = reg.get_tool_by_name("search_memories")
        assert tool is not None
        assert tool.name == "search_memories"

    def test_get_tool_by_name_not_found(self):
        reg = MCPToolRegistry()
        assert reg.get_tool_by_name("nonexistent") is None

    def test_list_tools_all(self):
        reg = MCPToolRegistry()
        reg.register_tool("t1", "d1", MCPToolCategory.READ, lambda a, c: None)
        reg.register_tool("t2", "d2", MCPToolCategory.WRITE, lambda a, c: None)
        reg.register_tool("t3", "d3", MCPToolCategory.READ, lambda a, c: None)
        assert reg.tool_count() == 3

    def test_list_tools_by_category(self):
        reg = MCPToolRegistry()
        reg.register_tool("t1", "d1", MCPToolCategory.READ, lambda a, c: None)
        reg.register_tool("t2", "d2", MCPToolCategory.WRITE, lambda a, c: None)
        reg.register_tool("t3", "d3", MCPToolCategory.READ, lambda a, c: None)
        read_tools = reg.list_tools(category=MCPToolCategory.READ)
        assert len(read_tools) == 2

    def test_create_binding(self):
        reg = MCPToolRegistry()
        reg.register_tool("t1", "d1", MCPToolCategory.READ, lambda a, c: None)
        tool = reg.get_tool_by_name("t1")
        binding = reg.create_binding(tool.tool_id, "WS-1")
        assert binding.workspace_id == "WS-1"
        assert reg.binding_count() == 1

    def test_get_bindings_for_workspace(self):
        reg = MCPToolRegistry()
        reg.register_tool("t1", "d1", MCPToolCategory.READ, lambda a, c: None)
        reg.register_tool("t2", "d2", MCPToolCategory.WRITE, lambda a, c: None)
        t1 = reg.get_tool_by_name("t1")
        t2 = reg.get_tool_by_name("t2")
        reg.create_binding(t1.tool_id, "WS-1")
        reg.create_binding(t2.tool_id, "WS-1")
        reg.create_binding(t1.tool_id, "WS-2")
        ws1_bindings = reg.get_bindings_for_workspace("WS-1")
        assert len(ws1_bindings) == 2

    def test_handler_retrieval(self):
        reg = MCPToolRegistry()
        handler = lambda args, ctx: {"result": 42}
        reg.register_tool("t1", "d1", MCPToolCategory.READ, handler)
        tool = reg.get_tool_by_name("t1")
        retrieved = reg.get_handler(tool.tool_id)
        assert retrieved is handler


# ── MCPRuntime ────────────────────────────────────────────────────────────

class TestMCPRuntime:
    def test_execute_tool_success(self):
        runtime = MCPRuntime()
        runtime.registry.register_tool(
            name="get_context",
            description="Get context",
            category=MCPToolCategory.READ,
            handler=lambda args, ctx: {"query": args.get("query", "")},
        )
        result = runtime.execute_tool("get_context", {"query": "test"})
        assert result.success is True
        assert result.data["query"] == "test"

    def test_execute_tool_not_found(self):
        runtime = MCPRuntime()
        result = runtime.execute_tool("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error

    def test_execute_tool_handler_error(self):
        runtime = MCPRuntime()
        runtime.registry.register_tool(
            name="fail_tool",
            description="Fails",
            category=MCPToolCategory.READ,
            handler=lambda args, ctx: (_ for _ in ()).throw(ValueError("boom")),
        )
        result = runtime.execute_tool("fail_tool", {})
        assert result.success is False
        assert "boom" in result.error

    def test_execute_tool_with_context(self):
        runtime = MCPRuntime()
        runtime.registry.register_tool(
            name="ctx_tool",
            description="Uses context",
            category=MCPToolCategory.READ,
            handler=lambda args, ctx: {"ws_id": ctx.context_id if ctx else None},
        )
        ctx = _make_workspace_context()
        result = runtime.execute_tool("ctx_tool", {}, workspace_context=ctx)
        assert result.success is True
        assert result.data["ws_id"] == "CTX-TEST"
        assert result.context_hash is not None

    def test_execute_tool_with_binding(self):
        runtime = MCPRuntime()
        runtime.registry.register_tool(
            name="bound_tool",
            description="Bound",
            category=MCPToolCategory.READ,
            handler=lambda args, ctx: {"bound": True},
        )
        tool = runtime.registry.get_tool_by_name("bound_tool")
        binding = runtime.registry.create_binding(tool.tool_id, "WS-1")
        result = runtime.execute_tool_with_binding(binding.binding_id, {})
        assert result.success is True

    def test_execute_tool_binding_not_found(self):
        runtime = MCPRuntime()
        result = runtime.execute_tool_with_binding("MCPB-FAKE", {})
        assert result.success is False
        assert "not found" in result.error

    def test_build_manifest(self):
        runtime = MCPRuntime()
        runtime.registry.register_tool("t1", "d1", MCPToolCategory.READ, lambda a, c: None)
        runtime.registry.register_tool("t2", "d2", MCPToolCategory.WRITE, lambda a, c: None)
        manifest = runtime.build_manifest(server_name="test", version="1.0.0")
        assert manifest.server_name == "test"
        assert manifest.version == "1.0.0"
        assert len(manifest.tools) == 2
        assert manifest.manifest_id.startswith("MCPM-")

    def test_multiple_tools(self):
        runtime = MCPRuntime()
        runtime.registry.register_tool("read_tool", "Reads", MCPToolCategory.READ, lambda a, c: {"r": True})
        runtime.registry.register_tool("write_tool", "Writes", MCPToolCategory.WRITE, lambda a, c: {"w": True})
        r1 = runtime.execute_tool("read_tool", {})
        r2 = runtime.execute_tool("write_tool", {})
        assert r1.success and r2.success

    def test_manifest_from_runtime(self):
        runtime = MCPRuntime()
        for i in range(5):
            runtime.registry.register_tool(
                f"tool_{i}", f"Tool {i}", MCPToolCategory.READ,
                lambda a, c: None,
            )
        manifest = runtime.build_manifest()
        assert len(manifest.tools) == 5
