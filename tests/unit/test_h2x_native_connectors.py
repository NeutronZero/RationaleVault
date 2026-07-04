"""
H2.x — Native Connector Tests.

Tests for all five vendor adapters: Claude, OpenCode, Codex, Cursor, Gemini.
"""
from __future__ import annotations

import json
import pytest

from rationalevault.runtime.models import Capability
from rationalevault.transport.models import TransportType
from rationalevault.vendor.connectors.claude import ClaudeAdapter
from rationalevault.vendor.connectors.opencode import OpenCodeAdapter
from rationalevault.vendor.connectors.codex import CodexAdapter
from rationalevault.vendor.connectors.cursor import CursorAdapter
from rationalevault.vendor.connectors.gemini import GeminiAdapter
from rationalevault.vendor.models import VendorAdapter, VendorManifest


# ── Shared Tests ─────────────────────────────────────────────────────────

class TestConnectorContracts:
    """Every adapter must satisfy the VendorAdapter contract."""

    @pytest.fixture(params=[
        ClaudeAdapter,
        OpenCodeAdapter,
        CodexAdapter,
        CursorAdapter,
        GeminiAdapter,
    ], ids=["claude", "opencode", "codex", "cursor", "gemini"])
    def adapter(self, request):
        return request.param()

    def test_manifest_is_frozen(self, adapter):
        m = adapter.manifest()
        with pytest.raises(AttributeError):
            m.name = "hacked"

    def test_manifest_id_format(self, adapter):
        m = adapter.manifest()
        assert m.manifest_id.startswith("VMNF-")

    def test_capability_mapping_is_frozen(self, adapter):
        cm = adapter.capability_mapping()
        with pytest.raises(AttributeError):
            cm.vendor_id = "hacked"

    def test_serialize_returns_bytes(self, adapter):
        result = adapter.serialize({"test": "data"})
        assert isinstance(result, bytes)

    def test_serialize_produces_valid_json(self, adapter):
        result = adapter.serialize({"test": "data"})
        parsed = json.loads(result)
        assert parsed["type"] == "workspace_package"
        assert parsed["data"]["test"] == "data"
        assert "format" in parsed

    def test_content_type_format(self, adapter):
        ct = adapter.content_type()
        assert ct.startswith("application/vnd.rationalevault.")

    def test_format_name_is_string(self, adapter):
        assert isinstance(adapter.format_name(), str)

    def test_capabilities_are_runtime_capabilities(self, adapter):
        m = adapter.manifest()
        for cap in m.supported_capabilities:
            assert isinstance(cap, Capability)

    def test_transports_are_transport_types(self, adapter):
        m = adapter.manifest()
        for t in m.supported_transports:
            assert isinstance(t, TransportType)


# ── Claude-Specific ──────────────────────────────────────────────────────

class TestClaudeAdapter:
    def test_manifest_details(self):
        m = ClaudeAdapter().manifest()
        assert m.name == "Claude"
        assert m.vendor_id == "anthropic"
        assert TransportType.MCP in m.supported_transports
        assert TransportType.CLI in m.supported_transports
        assert m.default_serializer == "ClaudeJSON"
        assert m.metadata["model_family"] == "claude-3"

    def test_capability_mapping(self):
        cm = ClaudeAdapter().capability_mapping()
        assert cm.vendor_to_runtime_cap("read:workspace") == Capability.READ_WORKSPACE
        assert cm.vendor_to_runtime_cap("read:memory") == Capability.READ_MEMORY
        assert cm.vendor_to_runtime_cap("suggest") == Capability.SUGGEST
        assert cm.vendor_to_runtime_cap("execute:skills") == Capability.EXECUTE_SKILLS

    def test_format_name(self):
        assert ClaudeAdapter().format_name() == "ClaudeJSON"


# ── OpenCode-Specific ────────────────────────────────────────────────────

class TestOpenCodeAdapter:
    def test_manifest_details(self):
        m = OpenCodeAdapter().manifest()
        assert m.name == "OpenCode"
        assert m.vendor_id == "opencode"
        assert TransportType.MCP in m.supported_transports
        assert TransportType.CLI in m.supported_transports
        assert m.default_serializer == "OpenCodeJSON"

    def test_capability_mapping(self):
        cm = OpenCodeAdapter().capability_mapping()
        assert cm.vendor_to_runtime_cap("read:workspace") == Capability.READ_WORKSPACE
        assert cm.vendor_to_runtime_cap("read:memory") == Capability.READ_MEMORY
        assert cm.vendor_to_runtime_cap("suggest") == Capability.SUGGEST


# ── Codex-Specific ───────────────────────────────────────────────────────

class TestCodexAdapter:
    def test_manifest_details(self):
        m = CodexAdapter().manifest()
        assert m.name == "Codex"
        assert m.vendor_id == "openai"
        assert TransportType.CLI in m.supported_transports
        assert TransportType.REST in m.supported_transports
        assert m.default_serializer == "CodexJSON"

    def test_capability_mapping(self):
        cm = CodexAdapter().capability_mapping()
        assert cm.vendor_to_runtime_cap("read:workspace") == Capability.READ_WORKSPACE
        assert cm.vendor_to_runtime_cap("read:memory") == Capability.READ_MEMORY


# ── Cursor-Specific ──────────────────────────────────────────────────────

class TestCursorAdapter:
    def test_manifest_details(self):
        m = CursorAdapter().manifest()
        assert m.name == "Cursor"
        assert m.vendor_id == "cursor"
        assert m.supported_transports == [TransportType.WEBSOCKET]
        assert m.default_serializer == "CursorJSON"

    def test_capability_mapping(self):
        cm = CursorAdapter().capability_mapping()
        assert cm.vendor_to_runtime_cap("read:workspace") == Capability.READ_WORKSPACE
        assert cm.vendor_to_runtime_cap("suggest") == Capability.SUGGEST


# ── Gemini-Specific ──────────────────────────────────────────────────────

class TestGeminiAdapter:
    def test_manifest_details(self):
        m = GeminiAdapter().manifest()
        assert m.name == "Gemini"
        assert m.vendor_id == "google"
        assert m.supported_transports == [TransportType.REST]
        assert m.default_serializer == "GeminiJSON"

    def test_capability_mapping(self):
        cm = GeminiAdapter().capability_mapping()
        assert cm.vendor_to_runtime_cap("read:workspace") == Capability.READ_WORKSPACE
        assert cm.vendor_to_runtime_cap("read:knowledge") == Capability.READ_KNOWLEDGE


# ── Adapter Registry ─────────────────────────────────────────────────────

class TestAdapterRegistry:
    """All adapters are discoverable and have unique vendor IDs."""

    def test_all_adapters_have_unique_vendor_ids(self):
        adapters = [
            ClaudeAdapter(),
            OpenCodeAdapter(),
            CodexAdapter(),
            CursorAdapter(),
            GeminiAdapter(),
        ]
        vendor_ids = [a.manifest().vendor_id for a in adapters]
        assert len(vendor_ids) == len(set(vendor_ids))

    def test_all_adapters_implement_abc(self):
        adapters = [
            ClaudeAdapter(),
            OpenCodeAdapter(),
            CodexAdapter(),
            CursorAdapter(),
            GeminiAdapter(),
        ]
        for adapter in adapters:
            assert isinstance(adapter, VendorAdapter)

    def test_all_manifests_have_unique_ids(self):
        adapters = [
            ClaudeAdapter(),
            OpenCodeAdapter(),
            CodexAdapter(),
            CursorAdapter(),
            GeminiAdapter(),
        ]
        ids = [a.manifest().manifest_id for a in adapters]
        assert len(ids) == len(set(ids))

    def test_serialize_produces_distinct_formats(self):
        adapters = {
            "Claude": ClaudeAdapter(),
            "OpenCode": OpenCodeAdapter(),
            "Codex": CodexAdapter(),
            "Cursor": CursorAdapter(),
            "Gemini": GeminiAdapter(),
        }
        formats = set()
        for name, adapter in adapters.items():
            result = adapter.serialize({"test": "data"})
            parsed = json.loads(result)
            formats.add(parsed["format"])
        assert len(formats) == 5
