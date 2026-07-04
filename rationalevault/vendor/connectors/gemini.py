"""
RationaleVault Native Connectors — Gemini (Google) adapter.

Gemini Connector: REST transport.
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


class GeminiAdapter(VendorAdapter):
    """
    Gemini (Google) vendor adapter.

    Supports REST transport.
    Maps Gemini-specific capabilities to runtime capabilities.
    Serializes to Gemini-compatible JSON format.
    """

    def manifest(self) -> VendorManifest:
        return VendorManifest(
            manifest_id=VendorManifest.generate_manifest_id(
                "Gemini", "google", "1.0.0",
            ),
            name="Gemini",
            vendor_id="google",
            version="1.0.0",
            supported_transports=[TransportType.REST],
            supported_capabilities=frozenset({
                Capability.READ_WORKSPACE,
                Capability.READ_MEMORY,
                Capability.SUGGEST,
                Capability.READ_KNOWLEDGE,
                Capability.READ_LINEAGE,
            }),
            default_serializer="GeminiJSON",
            metadata={
                "api_version": "2024-01-01",
                "model_family": "gemini",
            },
        )

    def capability_mapping(self) -> CapabilityMapping:
        return CapabilityMapping(
            vendor_id="google",
            vendor_to_runtime={
                "read:workspace": Capability.READ_WORKSPACE,
                "read:memory": Capability.READ_MEMORY,
                "read:knowledge": Capability.READ_KNOWLEDGE,
                "read:lineage": Capability.READ_LINEAGE,
                "suggest": Capability.SUGGEST,
            },
        )

    def serialize(self, package_dict: dict[str, Any]) -> bytes:
        """Serialize to Gemini-compatible JSON format."""
        gemini_format = {
            "type": "workspace_package",
            "data": package_dict,
            "format": "gemini_json",
        }
        return json.dumps(gemini_format, indent=2).encode("utf-8")

    def content_type(self) -> str:
        return "application/vnd.rationalevault.gemini+json"

    def format_name(self) -> str:
        return "GeminiJSON"
