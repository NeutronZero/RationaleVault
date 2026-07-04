"""
H2 — Vendor SDK Tests.

VendorManifest, VendorAdapter, CapabilityMapping.
"""
from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone

from rationalevault.runtime.models import Capability
from rationalevault.transport.models import TransportType
from rationalevault.vendor.models import (
    CapabilityMapping,
    VendorAdapter,
    VendorManifest,
    VendorStatus,
)


REF_TIME = "2026-06-26T12:00:00Z"


def _make_vendor_manifest(
    name: str = "Claude",
    vendor_id: str = "anthropic",
    version: str = "1.0.0",
    transports: list[TransportType] | None = None,
    capabilities: frozenset[Capability] | None = None,
) -> VendorManifest:
    manifest_id = VendorManifest.generate_manifest_id(name, vendor_id, version)
    return VendorManifest(
        manifest_id=manifest_id,
        name=name,
        vendor_id=vendor_id,
        version=version,
        supported_transports=transports or [TransportType.MCP],
        supported_capabilities=capabilities or frozenset({
            Capability.READ_WORKSPACE, Capability.READ_MEMORY,
            Capability.SUGGEST, Capability.EXECUTE_SKILLS,
        }),
    )


# ── VendorManifest ───────────────────────────────────────────────────────

class TestVendorManifest:
    def test_frozen(self):
        m = _make_vendor_manifest()
        with pytest.raises(AttributeError):
            m.name = "Hacked"

    def test_to_dict(self):
        m = _make_vendor_manifest()
        d = m.to_dict()
        assert d["name"] == "Claude"
        assert d["vendor_id"] == "anthropic"
        assert "MCP" in d["supported_transports"]
        assert d["status"] == "ACTIVE"

    def test_generate_id_deterministic(self):
        id1 = VendorManifest.generate_manifest_id("Claude", "anthropic", "1.0.0")
        id2 = VendorManifest.generate_manifest_id("Claude", "anthropic", "1.0.0")
        assert id1 == id2
        assert id1.startswith("VMNF-")

    def test_different_vendors_different_ids(self):
        id1 = VendorManifest.generate_manifest_id("Claude", "anthropic", "1.0.0")
        id2 = VendorManifest.generate_manifest_id("Codex", "openai", "1.0.0")
        assert id1 != id2

    def test_capabilities_in_dict(self):
        m = _make_vendor_manifest(
            capabilities=frozenset({Capability.READ_WORKSPACE, Capability.SUGGEST}),
        )
        d = m.to_dict()
        assert "READ_WORKSPACE" in d["supported_capabilities"]
        assert "SUGGEST" in d["supported_capabilities"]

    def test_multiple_transports(self):
        m = _make_vendor_manifest(
            transports=[TransportType.MCP, TransportType.CLI, TransportType.REST],
        )
        d = m.to_dict()
        assert len(d["supported_transports"]) == 3


# ── CapabilityMapping ────────────────────────────────────────────────────

class TestCapabilityMapping:
    def test_frozen(self):
        mapping = CapabilityMapping(vendor_id="anthropic")
        with pytest.raises(AttributeError):
            mapping.vendor_id = "hacked"

    def test_vendor_to_runtime(self):
        mapping = CapabilityMapping(
            vendor_id="anthropic",
            vendor_to_runtime={
                "read": Capability.READ_WORKSPACE,
                "suggest": Capability.SUGGEST,
            },
        )
        assert mapping.vendor_to_runtime_cap("read") == Capability.READ_WORKSPACE
        assert mapping.vendor_to_runtime_cap("suggest") == Capability.SUGGEST
        assert mapping.vendor_to_runtime_cap("unknown") is None

    def test_runtime_to_vendor(self):
        mapping = CapabilityMapping(
            vendor_id="anthropic",
            vendor_to_runtime={
                "read": Capability.READ_WORKSPACE,
                "suggest": Capability.SUGGEST,
            },
        )
        assert mapping.runtime_to_vendor_cap(Capability.READ_WORKSPACE) == "read"
        assert mapping.runtime_to_vendor_cap(Capability.SUGGEST) == "suggest"
        assert mapping.runtime_to_vendor_cap(Capability.EXECUTE_SKILLS) is None

    def test_to_dict(self):
        mapping = CapabilityMapping(
            vendor_id="anthropic",
            vendor_to_runtime={"read": Capability.READ_WORKSPACE},
        )
        d = mapping.to_dict()
        assert d["vendor_id"] == "anthropic"
        assert d["vendor_to_runtime"]["read"] == "READ_WORKSPACE"

    def test_empty_mapping(self):
        mapping = CapabilityMapping(vendor_id="anthropic")
        assert mapping.vendor_to_runtime_cap("anything") is None
        assert mapping.runtime_to_vendor_cap(Capability.READ_WORKSPACE) is None


# ── VendorAdapter (ABC) ──────────────────────────────────────────────────

class TestVendorAdapter:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            VendorAdapter()

    def test_concrete_implementation(self):
        class ClaudeAdapter(VendorAdapter):
            def manifest(self):
                return _make_vendor_manifest()
            def capability_mapping(self):
                return CapabilityMapping(
                    vendor_id="anthropic",
                    vendor_to_runtime={"read": Capability.READ_WORKSPACE},
                )
            def serialize(self, package_dict):
                return json.dumps(package_dict).encode("utf-8")
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "ClaudeJSON"

        adapter = ClaudeAdapter()
        assert adapter.format_name() == "ClaudeJSON"
        assert adapter.content_type() == "application/json"
        serialized = adapter.serialize({"test": "data"})
        assert isinstance(serialized, bytes)

    def test_supported_transports_default(self):
        class ClaudeAdapter(VendorAdapter):
            def manifest(self):
                return _make_vendor_manifest()
            def capability_mapping(self):
                return CapabilityMapping(vendor_id="anthropic")
            def serialize(self, d):
                return b"{}"
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"

        adapter = ClaudeAdapter()
        assert TransportType.MCP in adapter.supported_transports()
        assert TransportType.REST in adapter.supported_transports()

    def test_is_compatible(self):
        class MCPOnlyAdapter(VendorAdapter):
            def manifest(self):
                return _make_vendor_manifest(transports=[TransportType.MCP])
            def capability_mapping(self):
                return CapabilityMapping(vendor_id="anthropic")
            def serialize(self, d):
                return b"{}"
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"
            def supported_transports(self):
                return [TransportType.MCP]

        adapter = MCPOnlyAdapter()
        assert adapter.is_compatible(TransportType.MCP)
        assert not adapter.is_compatible(TransportType.REST)

    def test_manifest_propagation(self):
        m = _make_vendor_manifest()

        class ClaudeAdapter(VendorAdapter):
            def manifest(self):
                return m
            def capability_mapping(self):
                return CapabilityMapping(vendor_id="anthropic")
            def serialize(self, d):
                return b"{}"
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"

        adapter = ClaudeAdapter()
        assert adapter.manifest().vendor_id == "anthropic"

    def test_capability_mapping_propagation(self):
        cm = CapabilityMapping(
            vendor_id="anthropic",
            vendor_to_runtime={"read": Capability.READ_WORKSPACE},
        )

        class ClaudeAdapter(VendorAdapter):
            def manifest(self):
                return _make_vendor_manifest()
            def capability_mapping(self):
                return cm
            def serialize(self, d):
                return b"{}"
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"

        adapter = ClaudeAdapter()
        assert adapter.capability_mapping().vendor_to_runtime_cap("read") == Capability.READ_WORKSPACE
