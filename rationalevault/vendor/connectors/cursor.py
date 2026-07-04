"""
RationaleVault Native Connectors — Cursor adapter.

Cursor Connector: WebSocket transport.
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


class CursorAdapter(VendorAdapter):
    """
    Cursor vendor adapter.

    Supports WebSocket transport.
    Maps Cursor-specific capabilities to runtime capabilities.
    Serializes to Cursor-compatible JSON format.
    """

    def manifest(self) -> VendorManifest:
        return VendorManifest(
            manifest_id=VendorManifest.generate_manifest_id(
                "Cursor", "cursor", "1.0.0",
            ),
            name="Cursor",
            vendor_id="cursor",
            version="1.0.0",
            supported_transports=[TransportType.WEBSOCKET],
            supported_capabilities=frozenset({
                Capability.READ_WORKSPACE,
                Capability.READ_MEMORY,
                Capability.SUGGEST,
                Capability.READ_KNOWLEDGE,
            }),
            default_serializer="CursorJSON",
            metadata={
                "api_version": "2024-01-01",
                "model_family": "cursor",
            },
        )

    def capability_mapping(self) -> CapabilityMapping:
        return CapabilityMapping(
            vendor_id="cursor",
            vendor_to_runtime={
                "read:workspace": Capability.READ_WORKSPACE,
                "read:memory": Capability.READ_MEMORY,
                "read:knowledge": Capability.READ_KNOWLEDGE,
                "suggest": Capability.SUGGEST,
            },
        )

    def serialize(self, package_dict: dict[str, Any]) -> bytes:
        """Serialize to Cursor-compatible JSON format."""
        cursor_format = {
            "type": "workspace_package",
            "data": package_dict,
            "format": "cursor_json",
        }
        return json.dumps(cursor_format, indent=2).encode("utf-8")

    def content_type(self) -> str:
        return "application/vnd.rationalevault.cursor+json"

    def format_name(self) -> str:
        return "CursorJSON"
