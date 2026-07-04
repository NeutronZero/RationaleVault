"""RationaleVault Negotiation Engine — Deterministic transport capability negotiation.

NegotiationEngine produces TransportNegotiation from manifest + runtime state.

Design rules:
  - Pure functions, no I/O.
  - Deterministic: same inputs → identical negotiation outcome.
  - Rejects incompatible transports before sessions are created.
"""
from __future__ import annotations

from datetime import datetime, timezone

from rationalevault.transport.models import (
    NegotiationOutcome,
    RuntimeCompatibility,
    TransportCapabilities,
    TransportManifest,
    TransportNegotiation,
)


RUNTIME_VERSION = "2.3.0"
WORKSPACE_VERSION = "2.1.0"
SDK_VERSION = "1.0.0"


class NegotiationEngine:
    """Deterministic negotiation engine for transport compatibility."""

    @staticmethod
    def negotiate(
        manifest: TransportManifest,
        required_capabilities: TransportCapabilities | None = None,
        reference_time: datetime | None = None,
    ) -> TransportNegotiation:
        """Negotiate transport compatibility with the runtime.

        Args:
            manifest: Transport manifest to negotiate against.
            required_capabilities: Runtime's required capabilities.
            reference_time: Deterministic datetime override.

        Returns:
            TransportNegotiation with outcome, matched/missing capabilities, warnings.
        """
        now = (reference_time or datetime.now(timezone.utc)).isoformat()
        required = required_capabilities or TransportCapabilities()

        # Check runtime version compatibility
        runtime_compatible = RUNTIME_VERSION in manifest.supported_runtime_versions
        workspace_compatible = WORKSPACE_VERSION in manifest.supported_workspace_versions

        warnings: list[str] = []
        if not runtime_compatible and manifest.supported_runtime_versions:
            warnings.append(
                f"Runtime {RUNTIME_VERSION} not in supported versions: "
                f"{manifest.supported_runtime_versions}"
            )
        if not workspace_compatible and manifest.supported_workspace_versions:
            warnings.append(
                f"Workspace {WORKSPACE_VERSION} not in supported versions: "
                f"{manifest.supported_workspace_versions}"
            )

        # Check capability satisfaction
        matched: list[str] = []
        missing: list[str] = []

        cap_fields = [
            "supports_streaming", "supports_bidirectional", "supports_binary",
            "supports_incremental_updates", "supports_resume",
            "supports_tool_calls", "supports_large_context",
        ]

        for field_name in cap_fields:
            required_val = getattr(required, field_name)
            transport_val = getattr(manifest.capabilities, field_name)
            if required_val:
                if transport_val:
                    matched.append(field_name)
                else:
                    missing.append(field_name)

        # Check payload size
        if (required.max_payload_size_bytes > 0
                and manifest.capabilities.max_payload_size_bytes < required.max_payload_size_bytes):
            missing.append("max_payload_size_bytes")

        # Check concurrent sessions
        if (required.max_concurrent_sessions > 0
                and manifest.capabilities.max_concurrent_sessions < required.max_concurrent_sessions):
            missing.append("max_concurrent_sessions")

        # Determine outcome
        neg_id = TransportNegotiation.generate_negotiation_id(
            manifest.manifest_id, RUNTIME_VERSION, now
        )

        if missing:
            outcome = NegotiationOutcome.INCOMPATIBLE
        elif warnings:
            outcome = NegotiationOutcome.COMPATIBLE
        elif not runtime_compatible or not workspace_compatible:
            outcome = NegotiationOutcome.REQUIRES_MIGRATION
        else:
            outcome = NegotiationOutcome.COMPATIBLE

        return TransportNegotiation(
            negotiation_id=neg_id,
            transport_manifest_id=manifest.manifest_id,
            runtime_version=RUNTIME_VERSION,
            workspace_version=WORKSPACE_VERSION,
            transport_version=manifest.version,
            outcome=outcome,
            matched_capabilities=matched,
            missing_capabilities=missing,
            warnings=warnings,
            negotiated_at=now,
        )

    @staticmethod
    def check_compatibility(
        manifest: TransportManifest,
        reference_time: datetime | None = None,
    ) -> RuntimeCompatibility:
        """Produce a RuntimeCompatibility object for a transport.

        Args:
            manifest: Transport manifest to check.
            reference_time: Deterministic datetime override.

        Returns:
            RuntimeCompatibility with detailed version info.
        """
        warnings: list[str] = []
        migrations: list[str] = []

        runtime_ok = RUNTIME_VERSION in manifest.supported_runtime_versions
        workspace_ok = WORKSPACE_VERSION in manifest.supported_workspace_versions

        if not runtime_ok:
            warnings.append(f"Runtime {RUNTIME_VERSION} not in supported list")
            migrations.append(f"Transport must support runtime {RUNTIME_VERSION}")
        if not workspace_ok:
            warnings.append(f"Workspace {WORKSPACE_VERSION} not in supported list")
            migrations.append(f"Transport must support workspace {WORKSPACE_VERSION}")

        compatible = runtime_ok and workspace_ok

        return RuntimeCompatibility(
            runtime_version=RUNTIME_VERSION,
            workspace_version=WORKSPACE_VERSION,
            sdk_version=SDK_VERSION,
            transport_version=manifest.version,
            compatible=compatible,
            warnings=warnings,
            required_migrations=migrations,
        )
