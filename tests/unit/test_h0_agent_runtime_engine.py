"""
H0.1 — Agent Runtime Engine Tests.

AgentRuntime, SessionRegistry, CapabilityResolver, WorkspaceBinder, PackageStreamer.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from rationalevault.projections.workspace import WorkspaceState
from rationalevault.runtime.agent_runtime import AgentRuntime, Error, Success
from rationalevault.runtime.capability_resolver import CapabilityResolver
from rationalevault.runtime.models import (
    AgentCapabilities,
    AgentProfile,
    AgentSession,
    AgentStatus,
    AgentVendor,
    Capability,
    ProtocolVersion,
    SessionStatus,
    WorkspaceBinding,
)
from rationalevault.runtime.package_streamer import PackageStreamer
from rationalevault.runtime.session_registry import SessionRegistry
from rationalevault.runtime.workspace_binder import WorkspaceBinder
from rationalevault.workspace.models import Workspace, WorkspaceStatus


REF_TIME = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)


def _make_profile(
    name: str = "Claude",
    vendor: AgentVendor = AgentVendor.ANTHROPIC,
    capabilities: frozenset[Capability] | None = None,
) -> AgentProfile:
    profile_id = AgentProfile.generate_profile_id(name, vendor, REF_TIME.isoformat())
    return AgentProfile(
        profile_id=profile_id,
        name=name,
        vendor=vendor,
        model_id=f"{name.lower()}-4",
        capabilities=capabilities or frozenset({
            Capability.READ_WORKSPACE, Capability.READ_MEMORY,
            Capability.READ_LINEAGE, Capability.READ_KNOWLEDGE,
            Capability.SUGGEST, Capability.EXECUTE_SKILLS,
            Capability.VIEW_SYSTEM,
        }),
        status=AgentStatus.ACTIVE,
        created_at=REF_TIME.isoformat(),
        updated_at=REF_TIME.isoformat(),
    )


def _make_workspace() -> Workspace:
    ws_id = Workspace.generate_workspace_id("Test", REF_TIME.isoformat())
    return Workspace(
        workspace_id=ws_id, name="Test", description="Test",
        status=WorkspaceStatus.ACTIVE,
        agent_ids=["agent-a"], project_ids=["p1"],
        created_at=REF_TIME.isoformat(), updated_at=REF_TIME.isoformat(),
    )


def _make_state(**kwargs: any) -> WorkspaceState:
    defaults = dict(
        workspace_id="WS-TEST", workspace_name="Test",
        workspace_status="ACTIVE", compiled_at=REF_TIME.isoformat(),
    )
    defaults.update(kwargs)
    return WorkspaceState(**defaults)


def _make_session(status: SessionStatus = SessionStatus.CREATED) -> AgentSession:
    return AgentSession(
        session_id="AGS-001", profile_id="AGNT-001",
        workspace_id="WS-001", status=status,
        binding_id="WSB-001", started_at=REF_TIME.isoformat(),
        last_active_at=REF_TIME.isoformat(),
    )


def _make_binding() -> WorkspaceBinding:
    return WorkspaceBinding(
        binding_id="WSB-001", session_id="AGS-001",
        workspace_id="WS-001", role="PRIMARY",
        attached_at=REF_TIME.isoformat(),
    )


# ── SessionRegistry ──────────────────────────────────────────────────────

class TestSessionRegistry:
    def test_empty_registry(self):
        r = SessionRegistry()
        assert r.active_count == 0

    def test_add_session(self):
        s = _make_session()
        r = SessionRegistry().add_session(s)
        assert r.active_count == 1

    def test_active_sessions_exclude_closed(self):
        s1 = _make_session(status=SessionStatus.ATTACHED)
        s2 = _make_session(status=SessionStatus.CLOSED)
        # Need different session IDs
        s2 = AgentSession(
            session_id="AGS-002", profile_id=s2.profile_id,
            workspace_id=s2.workspace_id, status=SessionStatus.CLOSED,
            binding_id=s2.binding_id, started_at=s2.started_at,
            last_active_at=s2.last_active_at,
        )
        r = SessionRegistry().add_session(s1).add_session(s2)
        assert r.active_count == 1

    def test_get_session(self):
        s = _make_session()
        r = SessionRegistry().add_session(s)
        assert r.get_session("AGS-001") == s
        assert r.get_session("AGS-999") is None

    def test_has_open_session(self):
        s = _make_session(status=SessionStatus.ATTACHED)
        r = SessionRegistry().add_session(s)
        assert r.has_open_session("AGNT-001", "WS-001")

    def test_has_open_session_false_when_closed(self):
        s = _make_session(status=SessionStatus.CLOSED)
        r = SessionRegistry().add_session(s)
        assert not r.has_open_session("AGNT-001", "WS-001")

    def test_get_workspace_sessions(self):
        s1 = _make_session()
        s2 = AgentSession(
            session_id="AGS-002", profile_id="AGNT-002",
            workspace_id="WS-001", status=SessionStatus.ATTACHED,
            binding_id="WSB-002", started_at=REF_TIME.isoformat(),
            last_active_at=REF_TIME.isoformat(),
        )
        r = SessionRegistry().add_session(s1).add_session(s2)
        assert len(r.get_workspace_sessions("WS-001")) == 2

    def test_update_session(self):
        s = _make_session(status=SessionStatus.CREATED)
        r = SessionRegistry().add_session(s)
        updated = AgentSession(
            session_id=s.session_id, profile_id=s.profile_id,
            workspace_id=s.workspace_id, status=SessionStatus.ATTACHED,
            binding_id=s.binding_id, started_at=s.started_at,
            last_active_at=REF_TIME.isoformat(),
        )
        r2 = r.update_session(updated)
        assert r2.get_session(s.session_id).status == SessionStatus.ATTACHED

    def test_registry_frozen(self):
        r = SessionRegistry()
        with pytest.raises(AttributeError):
            r.sessions = ()


# ── CapabilityResolver ───────────────────────────────────────────────────

class TestCapabilityResolver:
    def test_resolve_from_profile(self):
        p = _make_profile()
        caps = CapabilityResolver.resolve(profile=p, reference_time=REF_TIME)
        assert Capability.READ_WORKSPACE in caps.effective

    def test_resolve_with_denials(self):
        p = _make_profile()
        denied = frozenset({Capability.EXECUTE_SKILLS})
        caps = CapabilityResolver.resolve(
            profile=p, denied=denied, reference_time=REF_TIME
        )
        assert Capability.EXECUTE_SKILLS not in caps.effective
        assert Capability.READ_WORKSPACE in caps.effective

    def test_resolve_from_profile_name(self):
        caps = CapabilityResolver.resolve_from_profile_name(
            "OBSERVER", reference_time=REF_TIME
        )
        assert Capability.READ_WORKSPACE in caps.effective
        assert Capability.EXECUTE_SKILLS not in caps.effective

    def test_resolve_unknown_profile(self):
        caps = CapabilityResolver.resolve_from_profile_name(
            "UNKNOWN", reference_time=REF_TIME
        )
        assert len(caps.effective) == 0

    def test_can_perform(self):
        p = _make_profile()
        caps = CapabilityResolver.resolve(profile=p, reference_time=REF_TIME)
        assert CapabilityResolver.can_perform(caps, Capability.READ_WORKSPACE)
        assert not CapabilityResolver.can_perform(caps, Capability.EXPORT_PACKAGE)

    def test_merge_capabilities(self):
        caps_a = AgentCapabilities(
            profile_id="A",
            granted=frozenset({Capability.READ_WORKSPACE}),
            denied=frozenset(),
        )
        caps_b = AgentCapabilities(
            profile_id="A",
            granted=frozenset({Capability.SUGGEST}),
            denied=frozenset(),
        )
        merged = CapabilityResolver.merge_capabilities(caps_a, caps_b)
        assert Capability.READ_WORKSPACE in merged.effective
        assert Capability.SUGGEST in merged.effective


# ── WorkspaceBinder ──────────────────────────────────────────────────────

class TestWorkspaceBinder:
    def test_create_session(self):
        b = _make_binding()
        session = WorkspaceBinder.create_session(
            profile_id="AGNT-001", workspace_id="WS-001",
            binding=b, reference_time=REF_TIME,
        )
        assert session.status == SessionStatus.CREATED
        assert session.profile_id == "AGNT-001"

    def test_attach(self):
        s = _make_session()
        updated, binding = WorkspaceBinder.attach(
            session=s, workspace_id="WS-001", reference_time=REF_TIME,
        )
        assert updated.status == SessionStatus.ATTACHED
        assert binding.workspace_id == "WS-001"

    def test_detach(self):
        s = _make_session(status=SessionStatus.ATTACHED)
        b = _make_binding()
        updated, closed = WorkspaceBinder.detach(
            session=s, binding=b, reference_time=REF_TIME,
        )
        assert updated.status == SessionStatus.DETACHED
        assert closed.detached_at is not None

    def test_close_session(self):
        s = _make_session(status=SessionStatus.ATTACHED)
        closed = WorkspaceBinder.close_session(
            session=s, packages_streamed=5, events_emitted=10,
            reference_time=REF_TIME,
        )
        assert closed.status == SessionStatus.CLOSED
        assert closed.ended_at is not None


# ── PackageStreamer ──────────────────────────────────────────────────────

class TestPackageStreamer:
    def test_build_runtime_context(self):
        s = _make_session()
        state = _make_state()
        ctx = PackageStreamer.build_runtime_context(
            session=s, workspace_state=state, reference_time=REF_TIME,
        )
        assert ctx.session_id == s.session_id
        assert ctx.agent_id == s.profile_id

    def test_stream_produces_package(self):
        s = _make_session(status=SessionStatus.ATTACHED)
        ws = _make_workspace()
        state = _make_state()
        ctx, pkg, payload = PackageStreamer.stream(
            session=s, workspace=ws, workspace_state=state,
            reference_time=REF_TIME,
        )
        assert pkg.workspace_id == ws.workspace_id
        assert pkg.agent_id == s.profile_id
        assert payload.session_id == s.session_id


# ── AgentRuntime ─────────────────────────────────────────────────────────

class TestAgentRuntime:
    def test_create_session(self):
        profile = _make_profile()
        ws = _make_workspace()
        result = AgentRuntime.create_session(
            profile=profile, workspace=ws, reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, binding, caps, event = result
        assert session.profile_id == profile.profile_id
        assert session.status == SessionStatus.CREATED
        assert event.session_id == session.session_id

    def test_create_session_protocol_mismatch(self):
        profile = _make_profile()
        ws = _make_workspace()
        result = AgentRuntime.create_session(
            profile=profile, workspace=ws,
            protocol_version="2.0.0", reference_time=REF_TIME,
        )
        assert isinstance(result, Error)
        assert "mismatch" in result.reason.lower()

    def test_create_session_inactive_profile(self):
        profile = AgentProfile(
            profile_id="AGNT-001", name="X", vendor=AgentVendor.LOCAL,
            model_id="x", status=AgentStatus.INACTIVE,
            created_at=REF_TIME.isoformat(), updated_at=REF_TIME.isoformat(),
        )
        ws = _make_workspace()
        result = AgentRuntime.create_session(
            profile=profile, workspace=ws, reference_time=REF_TIME,
        )
        assert isinstance(result, Error)
        assert "not active" in result.reason

    def test_attach_session(self):
        s = _make_session()
        ws = _make_workspace()
        caps = AgentCapabilities(
            profile_id="AGNT-001",
            granted=frozenset({Capability.READ_WORKSPACE}),
            resolved_at=REF_TIME.isoformat(),
        )
        result = AgentRuntime.attach(
            session=s, workspace=ws, capabilities=caps,
            reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, binding, event = result
        assert session.status == SessionStatus.ATTACHED

    def test_attach_wrong_status(self):
        s = _make_session(status=SessionStatus.ATTACHED)
        ws = _make_workspace()
        caps = AgentCapabilities(
            profile_id="AGNT-001", granted=frozenset(),
            resolved_at=REF_TIME.isoformat(),
        )
        result = AgentRuntime.attach(
            session=s, workspace=ws, capabilities=caps,
            reference_time=REF_TIME,
        )
        assert isinstance(result, Error)

    def test_pause_session(self):
        s = _make_session(status=SessionStatus.ATTACHED)
        result = AgentRuntime.pause(session=s, reference_time=REF_TIME)
        assert isinstance(result, tuple)
        session, event = result
        assert session.status == SessionStatus.PAUSED

    def test_pause_wrong_status(self):
        s = _make_session(status=SessionStatus.CREATED)
        result = AgentRuntime.pause(session=s, reference_time=REF_TIME)
        assert isinstance(result, Error)

    def test_resume_session(self):
        s = _make_session(status=SessionStatus.PAUSED)
        result = AgentRuntime.resume(session=s, reference_time=REF_TIME)
        assert isinstance(result, tuple)
        session, event = result
        assert session.status == SessionStatus.RESUMED

    def test_resume_wrong_status(self):
        s = _make_session(status=SessionStatus.ATTACHED)
        result = AgentRuntime.resume(session=s, reference_time=REF_TIME)
        assert isinstance(result, Error)

    def test_detach_session(self):
        s = _make_session(status=SessionStatus.ATTACHED)
        b = _make_binding()
        result = AgentRuntime.detach(
            session=s, binding=b, reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, binding, event = result
        assert session.status == SessionStatus.DETACHED

    def test_detach_closed_session(self):
        s = _make_session(status=SessionStatus.CLOSED)
        b = _make_binding()
        result = AgentRuntime.detach(
            session=s, binding=b, reference_time=REF_TIME,
        )
        assert isinstance(result, Error)

    def test_close_session(self):
        s = _make_session(status=SessionStatus.ATTACHED)
        result = AgentRuntime.close(
            session=s, packages_streamed=3, events_emitted=5,
            reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, event = result
        assert session.status == SessionStatus.CLOSED
        assert event.packages_streamed == 3

    def test_close_already_closed(self):
        s = _make_session(status=SessionStatus.CLOSED)
        result = AgentRuntime.close(session=s, reference_time=REF_TIME)
        assert isinstance(result, Error)

    def test_snapshot(self):
        s = _make_session()
        caps = AgentCapabilities(
            profile_id="AGNT-001",
            granted=frozenset({Capability.READ_WORKSPACE}),
            resolved_at=REF_TIME.isoformat(),
        )
        snap = AgentRuntime.snapshot(
            session=s, capabilities=caps, reference_time=REF_TIME,
        )
        assert snap.session_id == s.session_id
        assert snap.status == s.status.value

    def test_stream_package(self):
        s = _make_session(status=SessionStatus.ATTACHED)
        ws = _make_workspace()
        state = _make_state()
        result = AgentRuntime.stream_package(
            session=s, workspace=ws, workspace_state=state,
            reference_time=REF_TIME,
        )
        assert isinstance(result, tuple)
        session, pkg, ctx = result
        assert session.status == SessionStatus.STREAMING
        assert pkg.agent_id == s.profile_id

    def test_stream_wrong_status(self):
        s = _make_session(status=SessionStatus.CREATED)
        ws = _make_workspace()
        state = _make_state()
        result = AgentRuntime.stream_package(
            session=s, workspace=ws, workspace_state=state,
            reference_time=REF_TIME,
        )
        assert isinstance(result, Error)

    def test_full_lifecycle(self):
        """Create → Attach → Stream → Pause → Resume → Stream → Detach → Close."""
        profile = _make_profile()
        ws = _make_workspace()

        # Create
        r = AgentRuntime.create_session(
            profile=profile, workspace=ws, reference_time=REF_TIME,
        )
        assert isinstance(r, tuple)
        session, binding, caps, _ = r

        # Attach
        r = AgentRuntime.attach(
            session=session, workspace=ws, capabilities=caps,
            reference_time=REF_TIME,
        )
        assert isinstance(r, tuple)
        session, binding, _ = r

        # Stream
        state = _make_state()
        r = AgentRuntime.stream_package(
            session=session, workspace=ws, workspace_state=state,
            reference_time=REF_TIME,
        )
        assert isinstance(r, tuple)
        session, pkg, ctx = r

        # Pause
        r = AgentRuntime.pause(session=session, reference_time=REF_TIME)
        assert isinstance(r, tuple)
        session, _ = r

        # Resume
        r = AgentRuntime.resume(session=session, reference_time=REF_TIME)
        assert isinstance(r, tuple)
        session, _ = r

        # Stream again
        r = AgentRuntime.stream_package(
            session=session, workspace=ws, workspace_state=state,
            reference_time=REF_TIME,
        )
        assert isinstance(r, tuple)
        session, pkg, ctx = r

        # Detach
        r = AgentRuntime.detach(
            session=session, binding=binding, reference_time=REF_TIME,
        )
        assert isinstance(r, tuple)
        session, binding, _ = r

        # Close
        r = AgentRuntime.close(
            session=session, packages_streamed=2, events_emitted=4,
            reference_time=REF_TIME,
        )
        assert isinstance(r, tuple)
        session, event = r
        assert session.status == SessionStatus.CLOSED

    def test_event_payloads_frozen(self):
        from rationalevault.runtime.events import SessionCreatedPayload
        p = SessionCreatedPayload(
            session_id="AGS-001", profile_id="AGNT-001",
            workspace_id="WS-001", binding_id="WSB-001",
            created_at=REF_TIME.isoformat(),
        )
        with pytest.raises(AttributeError):
            p.session_id = "Hacked"
