"""
RationaleVault Native Connectors — Claude (Anthropic) adapter.

Claude Connector: MCP + CLI transports.
"""
from __future__ import annotations

import json
from typing import Any

from rationalevault.runtime.models import Capability
from rationalevault.transport.models import TransportType
from rationalevault.vendor.models import (
    CapabilityMapping,
    VendorAdapter,
    VendorManifest,
)


class ClaudeAdapter(VendorAdapter):
    """
    Claude (Anthropic) vendor adapter.

    Supports MCP and CLI transports.
    Maps Anthropic-specific capabilities to runtime capabilities.
    Serializes to Claude-compatible JSON format.
    """

    def manifest(self) -> VendorManifest:
        return VendorManifest(
            manifest_id=VendorManifest.generate_manifest_id(
                "Claude", "anthropic", "1.0.0",
            ),
            name="Claude",
            vendor_id="anthropic",
            version="1.0.0",
            supported_transports=[TransportType.MCP, TransportType.CLI],
            supported_capabilities=frozenset({
                Capability.READ_WORKSPACE,
                Capability.READ_MEMORY,
                Capability.SUGGEST,
                Capability.EXECUTE_SKILLS,
                Capability.READ_KNOWLEDGE,
                Capability.READ_LINEAGE,
            }),
            default_serializer="ClaudeJSON",
            metadata={
                "api_version": "2024-01-01",
                "model_family": "claude-3",
            },
        )

    def capability_mapping(self) -> CapabilityMapping:
        return CapabilityMapping(
            vendor_id="anthropic",
            vendor_to_runtime={
                "read:workspace": Capability.READ_WORKSPACE,
                "read:memory": Capability.READ_MEMORY,
                "read:knowledge": Capability.READ_KNOWLEDGE,
                "read:lineage": Capability.READ_LINEAGE,
                "suggest": Capability.SUGGEST,
                "execute:skills": Capability.EXECUTE_SKILLS,
            },
        )

    def serialize(self, package_dict: dict[str, Any]) -> bytes:
        """Serialize to Claude-compatible JSON format."""
        claude_format = {
            "type": "workspace_package",
            "data": package_dict,
            "format": "claude_json",
        }
        return json.dumps(claude_format, indent=2).encode("utf-8")

    def content_type(self) -> str:
        return "application/vnd.rationalevault.claude+json"

    def format_name(self) -> str:
        return "ClaudeJSON"
