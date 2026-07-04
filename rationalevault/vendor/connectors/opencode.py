"""
RationaleVault Native Connectors — OpenCode adapter.

OpenCode Connector: MCP + CLI transports.
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


class OpenCodeAdapter(VendorAdapter):
    """
    OpenCode vendor adapter.

    Supports MCP and CLI transports.
    Maps OpenCode-specific capabilities to runtime capabilities.
    Serializes to OpenCode-compatible JSON format.
    """

    def manifest(self) -> VendorManifest:
        return VendorManifest(
            manifest_id=VendorManifest.generate_manifest_id(
                "OpenCode", "opencode", "1.0.0",
            ),
            name="OpenCode",
            vendor_id="opencode",
            version="1.0.0",
            supported_transports=[TransportType.MCP, TransportType.CLI],
            supported_capabilities=frozenset({
                Capability.READ_WORKSPACE,
                Capability.READ_MEMORY,
                Capability.SUGGEST,
                Capability.EXECUTE_SKILLS,
                Capability.READ_KNOWLEDGE,
            }),
            default_serializer="OpenCodeJSON",
            metadata={
                "api_version": "2024-01-01",
                "model_family": "open-code",
            },
        )

    def capability_mapping(self) -> CapabilityMapping:
        return CapabilityMapping(
            vendor_id="opencode",
            vendor_to_runtime={
                "read:workspace": Capability.READ_WORKSPACE,
                "read:memory": Capability.READ_MEMORY,
                "read:knowledge": Capability.READ_KNOWLEDGE,
                "suggest": Capability.SUGGEST,
                "execute:skills": Capability.EXECUTE_SKILLS,
            },
        )

    def serialize(self, package_dict: dict[str, Any]) -> bytes:
        """Serialize to OpenCode-compatible JSON format."""
        opencode_format = {
            "type": "workspace_package",
            "data": package_dict,
            "format": "opencode_json",
        }
        return json.dumps(opencode_format, indent=2).encode("utf-8")

    def content_type(self) -> str:
        return "application/vnd.rationalevault.opencode+json"

    def format_name(self) -> str:
        return "OpenCodeJSON"
