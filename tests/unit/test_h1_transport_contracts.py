"""
H1.0 — Transport Contracts Tests.

Frozen dataclass contracts for the Transport SDK.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from rationalevault.transport.models import (
    NegotiationOutcome,
    RuntimeCompatibility,
    TransportCapabilities,
    TransportManifest,
    TransportNegotiation,
    TransportSession,
    TransportStatus,
    TransportType,
    WorkspacePackageSerializer,
)
from rationalevault.transport.events import (
    ConnectorAttachedPayload,
    ConnectorDetachedPayload,
    ConnectorNegotiatedPayload,
    ConnectorRegisteredPayload,
    ConnectorUnregisteredPayload,
    SCHEMA_VERSION,
    TransportPackageStreamedPayload,
)


REF_TIME = "2026-06-26T12:00:00Z"


# ── TransportCapabilities ────────────────────────────────────────────────

class TestTransportCapabilities:
    def test_frozen(self):
        c = TransportCapabilities()
        with pytest.raises(AttributeError):
            c.supports_streaming = True

    def test_defaults(self):
        c = TransportCapabilities()
        assert not c.supports_streaming
        assert not c.supports_bidirectional
        assert not c.supports_binary
        assert c.max_payload_size_bytes == 0
        assert c.max_concurrent_sessions == 1

    def test_to_dict(self):
        c = TransportCapabilities(
            supports_streaming=True, supports_bidirectional=True,
            max_payload_size_bytes=1024,
        )
        d = c.to_dict()
        assert d["supports_streaming"] is True
        assert d["supports_bidirectional"] is True
        assert d["max_payload_size_bytes"] == 1024

    def test_satisfies_all_met(self):
        c = TransportCapabilities(
            supports_streaming=True, supports_bidirectional=True,
        )
        required = TransportCapabilities(
            supports_streaming=True, supports_bidirectional=True,
        )
        assert c.satisfies(required)

    def test_satisfies_missing_streaming(self):
        c = TransportCapabilities(supports_streaming=False)
        required = TransportCapabilities(supports_streaming=True)
        assert not c.satisfies(required)

    def test_satisfies_payload_too_small(self):
        c = TransportCapabilities(max_payload_size_bytes=512)
        required = TransportCapabilities(max_payload_size_bytes=1024)
        assert not c.satisfies(required)

    def test_satisfies_empty_required(self):
        c = TransportCapabilities()
        required = TransportCapabilities()
        assert c.satisfies(required)

    def test_satisfies_concurrent_sessions(self):
        c = TransportCapabilities(max_concurrent_sessions=5)
        required = TransportCapabilities(max_concurrent_sessions=10)
        assert not c.satisfies(required)


# ── TransportManifest ────────────────────────────────────────────────────

class TestTransportManifest:
    def test_frozen(self):
        m = TransportManifest(
            manifest_id="TMNF-001", name="MCP",
            transport_type=TransportType.MCP, version="1.0.0",
            capabilities=TransportCapabilities(),
        )
        with pytest.raises(AttributeError):
            m.name = "Hacked"

    def test_to_dict(self):
        caps = TransportCapabilities(supports_streaming=True)
        m = TransportManifest(
            manifest_id="TMNF-001", name="MCP",
            transport_type=TransportType.MCP, version="1.0.0",
            capabilities=caps,
            supported_runtime_versions=["1.0.0", "2.0.0"],
        )
        d = m.to_dict()
        assert d["manifest_id"] == "TMNF-001"
        assert d["transport_type"] == "MCP"
        assert d["capabilities"]["supports_streaming"] is True
        assert "1.0.0" in d["supported_runtime_versions"]

    def test_generate_id_deterministic(self):
        id1 = TransportManifest.generate_manifest_id("MCP", TransportType.MCP, "1.0.0")
        id2 = TransportManifest.generate_manifest_id("MCP", TransportType.MCP, "1.0.0")
        assert id1 == id2
        assert id1.startswith("TMNF-")

    def test_different_names_different_ids(self):
        id1 = TransportManifest.generate_manifest_id("MCP", TransportType.MCP, "1.0.0")
        id2 = TransportManifest.generate_manifest_id("REST", TransportType.REST, "1.0.0")
        assert id1 != id2


# ── TransportNegotiation ─────────────────────────────────────────────────

class TestTransportNegotiation:
    def test_frozen(self):
        n = TransportNegotiation(
            negotiation_id="TNAG-001", transport_manifest_id="TMNF-001",
            runtime_version="2.2.0", workspace_version="2.1.0",
            transport_version="1.0.0", outcome=NegotiationOutcome.COMPATIBLE,
            negotiated_at=REF_TIME,
        )
        with pytest.raises(AttributeError):
            n.outcome = "Hacked"

    def test_is_compatible(self):
        n = TransportNegotiation(
            negotiation_id="TNAG-001", transport_manifest_id="TMNF-001",
            runtime_version="2.2.0", workspace_version="2.1.0",
            transport_version="1.0.0", outcome=NegotiationOutcome.COMPATIBLE,
            negotiated_at=REF_TIME,
        )
        assert n.is_compatible

    def test_is_not_compatible(self):
        n = TransportNegotiation(
            negotiation_id="TNAG-001", transport_manifest_id="TMNF-001",
            runtime_version="2.2.0", workspace_version="2.1.0",
            transport_version="1.0.0", outcome=NegotiationOutcome.INCOMPATIBLE,
            negotiated_at=REF_TIME,
        )
        assert not n.is_compatible

    def test_to_dict(self):
        n = TransportNegotiation(
            negotiation_id="TNAG-001", transport_manifest_id="TMNF-001",
            runtime_version="2.2.0", workspace_version="2.1.0",
            transport_version="1.0.0", outcome=NegotiationOutcome.COMPATIBLE,
            matched_capabilities=["streaming", "bidirectional"],
            missing_capabilities=["binary"],
            warnings=["Large payload may be slow"],
            negotiated_at=REF_TIME,
        )
        d = n.to_dict()
        assert d["outcome"] == "COMPATIBLE"
        assert "streaming" in d["matched_capabilities"]
        assert "binary" in d["missing_capabilities"]
        assert d["is_compatible"] is True

    def test_generate_id_deterministic(self):
        id1 = TransportNegotiation.generate_negotiation_id(
            "TMNF-001", "2.2.0", REF_TIME
        )
        id2 = TransportNegotiation.generate_negotiation_id(
            "TMNF-001", "2.2.0", REF_TIME
        )
        assert id1 == id2
        assert id1.startswith("TNAG-")


# ── TransportSession ─────────────────────────────────────────────────────

class TestTransportSession:
    def test_frozen(self):
        s = TransportSession(
            session_id="TSSN-001", transport_manifest_id="TMNF-001",
            negotiation_id="TNAG-001", agent_session_id="AGS-001",
            workspace_id="WS-001", status=TransportStatus.CREATED,
            created_at=REF_TIME, last_active_at=REF_TIME,
        )
        with pytest.raises(AttributeError):
            s.session_id = "Hacked"

    def test_to_dict(self):
        s = TransportSession(
            session_id="TSSN-001", transport_manifest_id="TMNF-001",
            negotiation_id="TNAG-001", agent_session_id="AGS-001",
            workspace_id="WS-001", status=TransportStatus.READY,
            packages_sent=5, bytes_transferred=1024,
            created_at=REF_TIME, last_active_at=REF_TIME,
        )
        d = s.to_dict()
        assert d["session_id"] == "TSSN-001"
        assert d["status"] == "READY"
        assert d["packages_sent"] == 5
        assert d["bytes_transferred"] == 1024

    def test_generate_id_deterministic(self):
        id1 = TransportSession.generate_session_id(
            "TMNF-001", "AGS-001", REF_TIME
        )
        id2 = TransportSession.generate_session_id(
            "TMNF-001", "AGS-001", REF_TIME
        )
        assert id1 == id2
        assert id1.startswith("TSSN-")


# ── WorkspacePackageSerializer (ABC) ────────────────────────────────────

class TestWorkspacePackageSerializer:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            WorkspacePackageSerializer()

    def test_concrete_implementation(self):
        class JsonSerializer(WorkspacePackageSerializer):
            def serialize(self, package_dict):
                import json
                return json.dumps(package_dict).encode("utf-8")
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"

        s = JsonSerializer()
        result = s.serialize({"test": "data"})
        assert isinstance(result, bytes)
        assert s.content_type() == "application/json"
        assert s.format_name() == "JSON"


# ── RuntimeCompatibility ─────────────────────────────────────────────────

class TestRuntimeCompatibility:
    def test_frozen(self):
        c = RuntimeCompatibility(
            runtime_version="2.2.0", workspace_version="2.1.0",
            sdk_version="1.0.0", transport_version="1.0.0",
            compatible=True,
        )
        with pytest.raises(AttributeError):
            c.compatible = False

    def test_compatible(self):
        c = RuntimeCompatibility(
            runtime_version="2.2.0", workspace_version="2.1.0",
            sdk_version="1.0.0", transport_version="1.0.0",
            compatible=True,
        )
        assert c.compatible

    def test_incompatible(self):
        c = RuntimeCompatibility(
            runtime_version="2.2.0", workspace_version="2.1.0",
            sdk_version="1.0.0", transport_version="1.0.0",
            compatible=False,
            warnings=["Major version mismatch"],
        )
        assert not c.compatible
        assert len(c.warnings) == 1

    def test_to_dict(self):
        c = RuntimeCompatibility(
            runtime_version="2.2.0", workspace_version="2.1.0",
            sdk_version="1.0.0", transport_version="1.0.0",
            compatible=True,
            warnings=["Deprecated feature used"],
            required_migrations=["Upgrade to v2.3"],
        )
        d = c.to_dict()
        assert d["compatible"] is True
        assert len(d["warnings"]) == 1
        assert len(d["required_migrations"]) == 1


# ── Event Payloads ───────────────────────────────────────────────────────

class TestTransportEvents:
    def test_connector_registered(self):
        p = ConnectorRegisteredPayload(
            manifest_id="TMNF-001", transport_type="MCP",
            name="MCP Transport", version="1.0.0", registered_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["manifest_id"] == "TMNF-001"
        assert d["schema_version"] == SCHEMA_VERSION

    def test_connector_negotiated(self):
        p = ConnectorNegotiatedPayload(
            negotiation_id="TNAG-001", manifest_id="TMNF-001",
            outcome="COMPATIBLE", matched_capabilities=["streaming"],
            negotiated_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["outcome"] == "COMPATIBLE"

    def test_connector_attached(self):
        p = ConnectorAttachedPayload(
            session_id="TSSN-001", transport_manifest_id="TMNF-001",
            agent_session_id="AGS-001", workspace_id="WS-001",
            attached_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["session_id"] == "TSSN-001"

    def test_package_streamed(self):
        p = TransportPackageStreamedPayload(
            session_id="TSSN-001", package_id="WSPKG-001",
            bytes_transferred=2048, serialization_format="JSON",
            streamed_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["bytes_transferred"] == 2048

    def test_connector_detached(self):
        p = ConnectorDetachedPayload(
            session_id="TSSN-001", workspace_id="WS-001",
            packages_sent=10, bytes_transferred=5120,
            detached_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["packages_sent"] == 10

    def test_connector_unregistered(self):
        p = ConnectorUnregisteredPayload(
            manifest_id="TMNF-001", reason="Deprecated",
            unregistered_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["reason"] == "Deprecated"

    def test_all_events_frozen(self):
        payloads = [
            ConnectorRegisteredPayload(manifest_id="TMNF-001", registered_at=REF_TIME),
            ConnectorNegotiatedPayload(negotiation_id="TNAG-001", manifest_id="TMNF-001",
                                       outcome="COMPATIBLE", negotiated_at=REF_TIME),
            ConnectorAttachedPayload(session_id="TSSN-001", transport_manifest_id="TMNF-001",
                                     agent_session_id="AGS-001", workspace_id="WS-001",
                                     attached_at=REF_TIME),
            TransportPackageStreamedPayload(session_id="TSSN-001", package_id="WSPKG-001",
                                            streamed_at=REF_TIME),
            ConnectorDetachedPayload(session_id="TSSN-001", workspace_id="WS-001",
                                     detached_at=REF_TIME),
            ConnectorUnregisteredPayload(manifest_id="TMNF-001", unregistered_at=REF_TIME),
        ]
        for p in payloads:
            with pytest.raises(AttributeError):
                p.schema_version = "2.0"
