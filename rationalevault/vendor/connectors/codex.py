"""
RationaleVault Native Connectors — Codex (OpenAI) adapter.

Codex Connector: CLI + REST transports.
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


class CodexAdapter(VendorAdapter):
    """
    Codex (OpenAI) vendor adapter.

    Supports CLI and REST transports.
    Maps Codex-specific capabilities to runtime capabilities.
    Serializes to Codex-compatible JSON format.
    """

    def manifest(self) -> VendorManifest:
        return VendorManifest(
            manifest_id=VendorManifest.generate_manifest_id(
                "Codex", "openai", "1.0.0",
            ),
            name="Codex",
            vendor_id="openai",
            version="1.0.0",
            supported_transports=[TransportType.CLI, TransportType.REST],
            supported_capabilities=frozenset({
                Capability.READ_WORKSPACE,
                Capability.READ_MEMORY,
                Capability.SUGGEST,
                Capability.READ_KNOWLEDGE,
                Capability.READ_LINEAGE,
            }),
            default_serializer="CodexJSON",
            metadata={
                "api_version": "2024-01-01",
                "model_family": "codex",
            },
        )

    def capability_mapping(self) -> CapabilityMapping:
        return CapabilityMapping(
            vendor_id="openai",
            vendor_to_runtime={
                "read:workspace": Capability.READ_WORKSPACE,
                "read:memory": Capability.READ_MEMORY,
                "read:knowledge": Capability.READ_KNOWLEDGE,
                "read:lineage": Capability.READ_LINEAGE,
                "suggest": Capability.SUGGEST,
            },
        )

    def serialize(self, package_dict: dict[str, Any]) -> bytes:
        """Serialize to Codex-compatible JSON format."""
        codex_format = {
            "type": "workspace_package",
            "data": package_dict,
            "format": "codex_json",
        }
        return json.dumps(codex_format, indent=2).encode("utf-8")

    def content_type(self) -> str:
        return "application/vnd.rationalevault.codex+json"

    def format_name(self) -> str:
        return "CodexJSON"
