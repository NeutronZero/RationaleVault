"""
H1.1 — Transport Runtime Tests.

NegotiationEngine, SerializationPipeline, TransportSessionManager, TransportRuntime.
"""
from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone

from rationalevault.transport.base_adapter import BaseTransportAdapter
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
from rationalevault.transport.negotiation_engine import NegotiationEngine
from rationalevault.transport.serialization_pipeline import SerializationPipeline
from rationalevault.transport.session_manager import TransportSessionManager
from rationalevault.transport.runtime import Error, Success, TransportRuntime


REF_TIME = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)


def _make_manifest(
    name: str = "MCP",
    transport_type: TransportType = TransportType.MCP,
    version: str = "1.0.0",
    capabilities: TransportCapabilities | None = None,
    supported_runtime: list[str] | None = None,
    supported_workspace: list[str] | None = None,
) -> TransportManifest:
    manifest_id = TransportManifest.generate_manifest_id(
        name, transport_type, version
    )
    return TransportManifest(
        manifest_id=manifest_id,
        name=name,
        transport_type=transport_type,
        version=version,
        capabilities=capabilities or TransportCapabilities(
            supports_streaming=True,
            supports_bidirectional=True,
            supports_resume=True,
            max_payload_size_bytes=10_000_000,
            max_concurrent_sessions=10,
        ),
        supported_runtime_versions=supported_runtime or ["2.3.0"],
        supported_workspace_versions=supported_workspace or ["2.1.0"],
    )


def _make_negotiation(
    outcome: NegotiationOutcome = NegotiationOutcome.COMPATIBLE,
) -> TransportNegotiation:
    return TransportNegotiation(
        negotiation_id="TNAG-001",
        transport_manifest_id="TMNF-001",
        runtime_version="2.3.0",
        workspace_version="2.1.0",
        transport_version="1.0.0",
        outcome=outcome,
        negotiated_at=REF_TIME.isoformat(),
    )


def _make_session(
    status: TransportStatus = TransportStatus.CREATED,
) -> TransportSession:
    return TransportSession(
        session_id="TSSN-001",
        transport_manifest_id="TMNF-001",
        negotiation_id="TNAG-001",
        agent_session_id="AGS-001",
        workspace_id="WS-001",
        status=status,
        created_at=REF_TIME.isoformat(),
        last_active_at=REF_TIME.isoformat(),
    )


# ── NegotiationEngine ────────────────────────────────────────────────────

class TestNegotiationEngine:
    def test_compatible_transport(self):
        m = _make_manifest()
        n = NegotiationEngine.negotiate(m, reference_time=REF_TIME)
        assert n.outcome == NegotiationOutcome.COMPATIBLE
        assert n.is_compatible

    def test_incompatible_missing_capabilities(self):
        m = _make_manifest(
            capabilities=TransportCapabilities(supports_streaming=False),
        )
        required = TransportCapabilities(supports_streaming=True)
        n = NegotiationEngine.negotiate(m, required, reference_time=REF_TIME)
        assert n.outcome == NegotiationOutcome.INCOMPATIBLE
        assert "supports_streaming" in n.missing_capabilities

    def test_incompatible_payload_too_small(self):
        m = _make_manifest(
            capabilities=TransportCapabilities(max_payload_size_bytes=100),
        )
        required = TransportCapabilities(max_payload_size_bytes=1000)
        n = NegotiationEngine.negotiate(m, required, reference_time=REF_TIME)
        assert n.outcome == NegotiationOutcome.INCOMPATIBLE

    def test_warnings_for_unsupported_runtime(self):
        m = _make_manifest(supported_runtime=["3.0.0"])
        n = NegotiationEngine.negotiate(m, reference_time=REF_TIME)
        assert len(n.warnings) > 0

    def test_deterministic(self):
        m = _make_manifest()
        n1 = NegotiationEngine.negotiate(m, reference_time=REF_TIME)
        n2 = NegotiationEngine.negotiate(m, reference_time=REF_TIME)
        assert n1.to_dict() == n2.to_dict()

    def test_check_compatibility(self):
        m = _make_manifest()
        c = NegotiationEngine.check_compatibility(m, reference_time=REF_TIME)
        assert c.compatible

    def test_check_compatibility_incompatible(self):
        m = _make_manifest(supported_runtime=["3.0.0"], supported_workspace=["3.0.0"])
        c = NegotiationEngine.check_compatibility(m, reference_time=REF_TIME)
        assert not c.compatible
        assert len(c.required_migrations) == 2

    def test_matched_capabilities(self):
        m = _make_manifest()
        required = TransportCapabilities(
            supports_streaming=True, supports_bidirectional=True,
        )
        n = NegotiationEngine.negotiate(m, required, reference_time=REF_TIME)
        assert "supports_streaming" in n.matched_capabilities
        assert "supports_bidirectional" in n.matched_capabilities

    def test_negotiation_id_deterministic(self):
        m = _make_manifest()
        n1 = NegotiationEngine.negotiate(m, reference_time=REF_TIME)
        n2 = NegotiationEngine.negotiate(m, reference_time=REF_TIME)
        assert n1.negotiation_id == n2.negotiation_id


# ── SerializationPipeline ────────────────────────────────────────────────

class TestSerializationPipeline:
    def setup_method(self):
        SerializationPipeline.clear()

    def test_register_and_serialize(self):
        class JsonSerializer(WorkspacePackageSerializer):
            def serialize(self, package_dict):
                return json.dumps(package_dict).encode("utf-8")
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"

        SerializationPipeline.register("JSON", JsonSerializer())
        data = {"test": "data", "number": 42}
        serialized, ct = SerializationPipeline.serialize(data, "JSON")
        assert isinstance(serialized, bytes)
        assert ct == "application/json"
        assert json.loads(serialized) == data

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown serialization format"):
            SerializationPipeline.serialize({}, "UNKNOWN")

    def test_list_serializers(self):
        class JsonSerializer(WorkspacePackageSerializer):
            def serialize(self, d):
                return b"{}"
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"

        SerializationPipeline.register("JSON", JsonSerializer())
        assert "JSON" in SerializationPipeline.list_serializers()

    def test_get_serializer(self):
        class JsonSerializer(WorkspacePackageSerializer):
            def serialize(self, d):
                return b"{}"
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"

        s = JsonSerializer()
        SerializationPipeline.register("JSON", s)
        assert SerializationPipeline.get("JSON") is s
        assert SerializationPipeline.get("UNKNOWN") is None

    def test_clear(self):
        class JsonSerializer(WorkspacePackageSerializer):
            def serialize(self, d):
                return b"{}"
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"

        SerializationPipeline.register("JSON", JsonSerializer())
        SerializationPipeline.clear()
        assert SerializationPipeline.list_serializers() == []


# ── TransportSessionManager ──────────────────────────────────────────────

class TestTransportSessionManager:
    def test_empty_manager(self):
        m = TransportSessionManager()
        assert m.active_count == 0

    def test_add_session(self):
        s = _make_session()
        m = TransportSessionManager().add_session(s)
        assert m.active_count == 1

    def test_active_sessions_exclude_closed(self):
        s1 = _make_session(status=TransportStatus.READY)
        s2 = TransportSession(
            session_id="TSSN-002", transport_manifest_id="TMNF-001",
            negotiation_id="TNAG-001", agent_session_id="AGS-002",
            workspace_id="WS-001", status=TransportStatus.CLOSED,
            created_at=REF_TIME.isoformat(), last_active_at=REF_TIME.isoformat(),
        )
        m = TransportSessionManager().add_session(s1).add_session(s2)
        assert m.active_count == 1

    def test_get_session(self):
        s = _make_session()
        m = TransportSessionManager().add_session(s)
        assert m.get_session("TSSN-001") == s
        assert m.get_session("TSSN-999") is None

    def test_get_by_agent_session(self):
        s = _make_session()
        m = TransportSessionManager().add_session(s)
        assert m.get_by_agent_session("AGS-001") == s
        assert m.get_by_agent_session("AGS-999") is None

    def test_get_by_workspace(self):
        s1 = _make_session()
        s2 = TransportSession(
            session_id="TSSN-002", transport_manifest_id="TMNF-001",
            negotiation_id="TNAG-001", agent_session_id="AGS-002",
            workspace_id="WS-002", status=TransportStatus.READY,
            created_at=REF_TIME.isoformat(), last_active_at=REF_TIME.isoformat(),
        )
        m = TransportSessionManager().add_session(s1).add_session(s2)
        assert len(m.get_by_workspace("WS-001")) == 1
        assert len(m.get_by_workspace("WS-002")) == 1

    def test_get_by_transport(self):
        s = _make_session()
        m = TransportSessionManager().add_session(s)
        assert len(m.get_by_transport("TMNF-001")) == 1

    def test_has_active_session(self):
        s = _make_session(status=TransportStatus.READY)
        m = TransportSessionManager().add_session(s)
        assert m.has_active_session("AGS-001")
        assert not m.has_active_session("AGS-999")

    def test_update_session(self):
        s = _make_session(status=TransportStatus.CREATED)
        m = TransportSessionManager().add_session(s)
        updated = TransportSession(
            session_id=s.session_id, transport_manifest_id=s.transport_manifest_id,
            negotiation_id=s.negotiation_id, agent_session_id=s.agent_session_id,
            workspace_id=s.workspace_id, status=TransportStatus.READY,
            created_at=s.created_at, last_active_at=REF_TIME.isoformat(),
        )
        m2 = m.update_session(updated)
        assert m2.get_session(s.session_id).status == TransportStatus.READY

    def test_manager_frozen(self):
        m = TransportSessionManager()
        with pytest.raises(AttributeError):
            m.sessions = ()


# ── TransportRuntime ─────────────────────────────────────────────────────

class TestTransportRuntime:
    def test_register_transport(self):
        m = _make_manifest()
        manifest, event = TransportRuntime.register_transport(
            m, reference_time=REF_TIME,
        )
        assert manifest.manifest_id == m.manifest_id
        assert event.transport_type == "MCP"

    def test_negotiate_success(self):
        m = _make_manifest()
        result = TransportRuntime.negotiate(m, reference_time=REF_TIME)
        assert isinstance(result, tuple)
        negotiation, event = result
        assert negotiation.is_compatible
        assert event.outcome == "COMPATIBLE"

    def test_negotiate_incompatible(self):
        m = _make_manifest(
            capabilities=TransportCapabilities(supports_streaming=False),
        )
        required = TransportCapabilities(supports_streaming=True)
        result = TransportRuntime.negotiate(m, reference_time=REF_TIME)
        # Should still succeed but with missing capabilities
        assert isinstance(result, tuple)

    def test_attach_success(self):
        m = _make_manifest()
        n = _make_negotiation()
        result = TransportRuntime.attach(
            manifest=m, negotiation=n,
            agent_session_id="AGS-001", workspace_id="WS-001",
            reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, event = result
        assert session.status == TransportStatus.CREATED
        assert event.agent_session_id == "AGS-001"

    def test_attach_incompatible_negotiation(self):
        m = _make_manifest()
        n = _make_negotiation(outcome=NegotiationOutcome.INCOMPATIBLE)
        result = TransportRuntime.attach(
            manifest=m, negotiation=n,
            agent_session_id="AGS-001", workspace_id="WS-001",
            reference_time=REF_TIME,
        )
        assert isinstance(result, Error)

    def test_stream_package(self):
        s = _make_session(status=TransportStatus.CREATED)

        class JsonSerializer(WorkspacePackageSerializer):
            def serialize(self, d):
                return json.dumps(d).encode("utf-8")
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"

        SerializationPipeline.clear()
        SerializationPipeline.register("JSON", JsonSerializer())

        result = TransportRuntime.stream_package(
            session=s,
            package_dict={"package_id": "WSPKG-001", "test": "data"},
            format_name="JSON",
            reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, event, serialized = result
        assert session.status == TransportStatus.STREAMING
        assert session.packages_sent == 1
        assert len(serialized) > 0

    def test_stream_closed_session(self):
        s = _make_session(status=TransportStatus.CLOSED)
        result = TransportRuntime.stream_package(
            session=s, package_dict={}, format_name="JSON",
            reference_time=REF_TIME,
        )
        assert isinstance(result, Error)

    def test_stream_unknown_format(self):
        s = _make_session()
        SerializationPipeline.clear()
        result = TransportRuntime.stream_package(
            session=s, package_dict={}, format_name="UNKNOWN",
            reference_time=REF_TIME,
        )
        assert isinstance(result, Error)

    def test_detach(self):
        s = _make_session(status=TransportStatus.READY)
        result = TransportRuntime.detach(s, reference_time=REF_TIME)
        assert isinstance(result, tuple)
        session, event = result
        assert session.status == TransportStatus.CLOSED
        assert event.detached_at is not None

    def test_detach_closed_session(self):
        s = _make_session(status=TransportStatus.CLOSED)
        result = TransportRuntime.detach(s, reference_time=REF_TIME)
        assert isinstance(result, Error)

    def test_unregister_transport(self):
        m = _make_manifest()
        event = TransportRuntime.unregister_transport(
            m, reason="Deprecated", reference_time=REF_TIME,
        )
        assert event.manifest_id == m.manifest_id
        assert event.reason == "Deprecated"

    def test_full_lifecycle(self):
        """Register → Negotiate → Attach → Stream → Detach → Unregister."""
        SerializationPipeline.clear()

        class JsonSerializer(WorkspacePackageSerializer):
            def serialize(self, d):
                return json.dumps(d).encode("utf-8")
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "JSON"

        SerializationPipeline.register("JSON", JsonSerializer())

        m = _make_manifest()

        # Register
        _, event = TransportRuntime.register_transport(m, reference_time=REF_TIME)
        assert event.transport_type == "MCP"

        # Negotiate
        result = TransportRuntime.negotiate(m, reference_time=REF_TIME)
        assert isinstance(result, tuple)
        negotiation, event = result

        # Attach
        result = TransportRuntime.attach(
            manifest=m, negotiation=negotiation,
            agent_session_id="AGS-001", workspace_id="WS-001",
            reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, event = result

        # Stream
        result = TransportRuntime.stream_package(
            session=session,
            package_dict={"package_id": "WSPKG-001"},
            format_name="JSON",
            reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, event, serialized = result
        assert session.packages_sent == 1

        # Stream again
        result = TransportRuntime.stream_package(
            session=session,
            package_dict={"package_id": "WSPKG-002"},
            format_name="JSON",
            reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, event, serialized = result
        assert session.packages_sent == 2

        # Detach
        result = TransportRuntime.detach(session, reference_time=REF_TIME)
        assert isinstance(result, tuple)
        session, event = result
        assert session.status == TransportStatus.CLOSED

        # Unregister
        event = TransportRuntime.unregister_transport(m, reference_time=REF_TIME)
        assert event.manifest_id == m.manifest_id


# ── BaseTransportAdapter (ABC) ───────────────────────────────────────────

class TestBaseTransportAdapter:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            BaseTransportAdapter()

    def test_concrete_implementation(self):
        class MockTransport(BaseTransportAdapter):
            def manifest(self):
                return _make_manifest()
            def capabilities(self):
                return TransportCapabilities(supports_streaming=True)
            def serialize(self, package_dict):
                return json.dumps(package_dict).encode("utf-8")
            def content_type(self):
                return "application/json"
            def format_name(self):
                return "MockJSON"

        t = MockTransport()
        assert t.format_name() == "MockJSON"
        assert t.content_type() == "application/json"
        serialized = t.serialize({"test": "data"})
        assert isinstance(serialized, bytes)
