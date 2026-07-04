"""
H0.0 — Agent Runtime Contracts Tests.

Frozen dataclass contracts for agent runtime. No behavior.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from rationalevault.runtime.models import (
    AgentCapabilities,
    AgentProfile,
    AgentSession,
    AgentStatus,
    AgentVendor,
    Capability,
    CapabilityProfile,
    CAPABILITY_PROFILES,
    ProtocolVersion,
    RuntimeContext,
    SessionSnapshot,
    SessionStatus,
    WorkspaceBinding,
)
from rationalevault.runtime.events import (
    PackageStreamedPayload,
    SCHEMA_VERSION,
    SessionAttachedPayload,
    SessionClosedPayload,
    SessionCreatedPayload,
    SessionDetachedPayload,
    SessionPausedPayload,
    SessionResumedPayload,
)


REF_TIME = "2026-06-26T12:00:00Z"


# ── AgentProfile ─────────────────────────────────────────────────────────

class TestAgentProfile:
    def test_frozen(self):
        p = AgentProfile(
            profile_id="AGNT-001", name="Claude", vendor=AgentVendor.ANTHROPIC,
            model_id="claude-4", created_at=REF_TIME, updated_at=REF_TIME,
        )
        with pytest.raises(AttributeError):
            p.name = "Hacked"

    def test_to_dict(self):
        p = AgentProfile(
            profile_id="AGNT-001", name="Claude", vendor=AgentVendor.ANTHROPIC,
            model_id="claude-4",
            capabilities=frozenset({Capability.READ_WORKSPACE, Capability.SUGGEST}),
            created_at=REF_TIME, updated_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["profile_id"] == "AGNT-001"
        assert d["name"] == "Claude"
        assert d["vendor"] == "ANTHROPIC"
        assert d["model_id"] == "claude-4"
        assert "READ_WORKSPACE" in d["capabilities"]
        assert "SUGGEST" in d["capabilities"]

    def test_generate_id_deterministic(self):
        id1 = AgentProfile.generate_profile_id("Claude", AgentVendor.ANTHROPIC, REF_TIME)
        id2 = AgentProfile.generate_profile_id("Claude", AgentVendor.ANTHROPIC, REF_TIME)
        assert id1 == id2
        assert id1.startswith("AGNT-")

    def test_different_names_different_ids(self):
        id1 = AgentProfile.generate_profile_id("Claude", AgentVendor.ANTHROPIC, REF_TIME)
        id2 = AgentProfile.generate_profile_id("Codex", AgentVendor.OPENAI, REF_TIME)
        assert id1 != id2

    def test_default_status_active(self):
        p = AgentProfile(
            profile_id="AGNT-001", name="X", vendor=AgentVendor.LOCAL,
            model_id="local", created_at=REF_TIME, updated_at=REF_TIME,
        )
        assert p.status == AgentStatus.ACTIVE

    def test_capabilities_frozen_set(self):
        caps = frozenset({Capability.READ_WORKSPACE})
        p = AgentProfile(
            profile_id="AGNT-001", name="X", vendor=AgentVendor.LOCAL,
            model_id="m", capabilities=caps, created_at=REF_TIME, updated_at=REF_TIME,
        )
        assert Capability.READ_WORKSPACE in p.capabilities


# ── AgentCapabilities ────────────────────────────────────────────────────

class TestAgentCapabilities:
    def test_frozen(self):
        c = AgentCapabilities(profile_id="AGNT-001", resolved_at=REF_TIME)
        with pytest.raises(AttributeError):
            c.profile_id = "Hacked"

    def test_effective_capabilities(self):
        c = AgentCapabilities(
            profile_id="AGNT-001",
            granted=frozenset({Capability.READ_WORKSPACE, Capability.SUGGEST}),
            denied=frozenset({Capability.SUGGEST}),
            resolved_at=REF_TIME,
        )
        assert c.effective == frozenset({Capability.READ_WORKSPACE})
        assert Capability.SUGGEST not in c.effective

    def test_has_method(self):
        c = AgentCapabilities(
            profile_id="AGNT-001",
            granted=frozenset({Capability.READ_WORKSPACE}),
            resolved_at=REF_TIME,
        )
        assert c.has(Capability.READ_WORKSPACE)
        assert not c.has(Capability.SUGGEST)

    def test_to_dict(self):
        c = AgentCapabilities(
            profile_id="AGNT-001",
            granted=frozenset({Capability.READ_WORKSPACE, Capability.SUGGEST}),
            denied=frozenset(),
            resolved_at=REF_TIME,
        )
        d = c.to_dict()
        assert d["profile_id"] == "AGNT-001"
        assert "READ_WORKSPACE" in d["granted"]
        assert "SUGGEST" in d["granted"]
        assert len(d["effective"]) == 2


# ── WorkspaceBinding ─────────────────────────────────────────────────────

class TestWorkspaceBinding:
    def test_frozen(self):
        b = WorkspaceBinding(
            binding_id="WSB-001", session_id="AGS-001",
            workspace_id="WS-001", role="PRIMARY", attached_at=REF_TIME,
        )
        with pytest.raises(AttributeError):
            b.role = "Hacked"

    def test_to_dict(self):
        b = WorkspaceBinding(
            binding_id="WSB-001", session_id="AGS-001",
            workspace_id="WS-001", role="PRIMARY", attached_at=REF_TIME,
        )
        d = b.to_dict()
        assert d["binding_id"] == "WSB-001"
        assert d["role"] == "PRIMARY"
        assert d["detached_at"] is None

    def test_generate_id_deterministic(self):
        id1 = WorkspaceBinding.generate_binding_id("AGS-001", "WS-001")
        id2 = WorkspaceBinding.generate_binding_id("AGS-001", "WS-001")
        assert id1 == id2
        assert id1.startswith("WSB-")


# ── RuntimeContext ───────────────────────────────────────────────────────

class TestRuntimeContext:
    def test_frozen(self):
        c = RuntimeContext(
            context_id="RTC-001", session_id="AGS-001",
            binding_id="WSB-001", workspace_id="WS-001",
            agent_id="AGNT-001", created_at=REF_TIME,
        )
        with pytest.raises(AttributeError):
            c.session_id = "Hacked"

    def test_to_dict(self):
        c = RuntimeContext(
            context_id="RTC-001", session_id="AGS-001",
            binding_id="WSB-001", workspace_id="WS-001",
            agent_id="AGNT-001",
            goals=["g1"], open_decisions=["DEC-001"],
            capabilities=frozenset({Capability.READ_WORKSPACE}),
            created_at=REF_TIME,
        )
        d = c.to_dict()
        assert d["context_id"] == "RTC-001"
        assert d["goals"] == ["g1"]
        assert "READ_WORKSPACE" in d["capabilities"]

    def test_generate_id_deterministic(self):
        id1 = RuntimeContext.generate_context_id("AGS-001", REF_TIME)
        id2 = RuntimeContext.generate_context_id("AGS-001", REF_TIME)
        assert id1 == id2
        assert id1.startswith("RTC-")


# ── SessionSnapshot ──────────────────────────────────────────────────────

class TestSessionSnapshot:
    def test_frozen(self):
        s = SessionSnapshot(
            snapshot_id="SSSN-001", session_id="AGS-001",
            workspace_id="WS-001", agent_id="AGNT-001",
            status="ATTACHED", created_at=REF_TIME,
        )
        with pytest.raises(AttributeError):
            s.session_id = "Hacked"

    def test_to_dict(self):
        s = SessionSnapshot(
            snapshot_id="SSSN-001", session_id="AGS-001",
            workspace_id="WS-001", agent_id="AGNT-001",
            status="ATTACHED",
            capabilities=frozenset({Capability.READ_WORKSPACE}),
            packages_streamed=5, events_emitted=10,
            created_at=REF_TIME,
        )
        d = s.to_dict()
        assert d["packages_streamed"] == 5
        assert d["events_emitted"] == 10
        assert "READ_WORKSPACE" in d["capabilities"]

    def test_generate_id_deterministic(self):
        id1 = SessionSnapshot.generate_snapshot_id("AGS-001", REF_TIME)
        id2 = SessionSnapshot.generate_snapshot_id("AGS-001", REF_TIME)
        assert id1 == id2
        assert id1.startswith("SSSN-")


# ── AgentSession ─────────────────────────────────────────────────────────

class TestAgentSession:
    def test_frozen(self):
        s = AgentSession(
            session_id="AGS-001", profile_id="AGNT-001",
            workspace_id="WS-001", status=SessionStatus.CREATED,
            binding_id="WSB-001", started_at=REF_TIME,
            last_active_at=REF_TIME,
        )
        with pytest.raises(AttributeError):
            s.session_id = "Hacked"

    def test_to_dict(self):
        s = AgentSession(
            session_id="AGS-001", profile_id="AGNT-001",
            workspace_id="WS-001", status=SessionStatus.ATTACHED,
            binding_id="WSB-001", context_id="RTC-001",
            snapshot_id="SSSN-001", protocol_version="1.0",
            started_at=REF_TIME, last_active_at=REF_TIME,
        )
        d = s.to_dict()
        assert d["session_id"] == "AGS-001"
        assert d["status"] == "ATTACHED"
        assert d["context_id"] == "RTC-001"

    def test_generate_id_deterministic(self):
        id1 = AgentSession.generate_session_id("AGNT-001", "WS-001", REF_TIME)
        id2 = AgentSession.generate_session_id("AGNT-001", "WS-001", REF_TIME)
        assert id1 == id2
        assert id1.startswith("AGS-")

    def test_default_protocol_version(self):
        s = AgentSession(
            session_id="AGS-001", profile_id="AGNT-001",
            workspace_id="WS-001", status=SessionStatus.CREATED,
            binding_id="WSB-001", started_at=REF_TIME,
            last_active_at=REF_TIME,
        )
        assert s.protocol_version == "1.0"


# ── ProtocolVersion ──────────────────────────────────────────────────────

class TestProtocolVersion:
    def test_parse(self):
        v = ProtocolVersion.parse("2.1.0")
        assert v.major == 2
        assert v.minor == 1
        assert v.patch == 0

    def test_str(self):
        v = ProtocolVersion(2, 1, 0)
        assert str(v) == "2.1.0"

    def test_compatible_same_major(self):
        v1 = ProtocolVersion(2, 0, 0)
        v2 = ProtocolVersion(2, 5, 3)
        assert v1.is_compatible(v2)

    def test_incompatible_different_major(self):
        v1 = ProtocolVersion(1, 0, 0)
        v2 = ProtocolVersion(2, 0, 0)
        assert not v1.is_compatible(v2)

    def test_frozen(self):
        v = ProtocolVersion(1, 0, 0)
        with pytest.raises(AttributeError):
            v.major = 2

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            ProtocolVersion.parse("1.0")


# ── Capability Profiles ─────────────────────────────────────────────────

class TestCapabilityProfiles:
    def test_observer_profile(self):
        caps = CAPABILITY_PROFILES[CapabilityProfile.OBSERVER]
        assert Capability.READ_WORKSPACE in caps
        assert Capability.EXECUTE_SKILLS not in caps
        assert Capability.SUGGEST not in caps

    def test_planner_profile(self):
        caps = CAPABILITY_PROFILES[CapabilityProfile.PLANNER]
        assert Capability.READ_WORKSPACE in caps
        assert Capability.SUGGEST in caps
        assert Capability.EXECUTE_SKILLS not in caps

    def test_researcher_profile(self):
        caps = CAPABILITY_PROFILES[CapabilityProfile.RESEARCHER]
        assert Capability.CREATE_REFLECTION in caps
        assert Capability.EXECUTE_SKILLS not in caps

    def test_executor_profile(self):
        caps = CAPABILITY_PROFILES[CapabilityProfile.EXECUTOR]
        assert Capability.EXECUTE_SKILLS in caps
        assert Capability.EXPORT_PACKAGE in caps

    def test_administrator_profile(self):
        caps = CAPABILITY_PROFILES[CapabilityProfile.ADMINISTRATOR]
        assert len(caps) == len(Capability)

    def test_all_profiles_are_frozensets(self):
        for profile, caps in CAPABILITY_PROFILES.items():
            assert isinstance(caps, frozenset)


# ── Event Payloads ───────────────────────────────────────────────────────

class TestEventPayloads:
    def test_session_created(self):
        p = SessionCreatedPayload(
            session_id="AGS-001", profile_id="AGNT-001",
            workspace_id="WS-001", binding_id="WSB-001",
            created_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["session_id"] == "AGS-001"
        assert d["schema_version"] == SCHEMA_VERSION

    def test_session_attached(self):
        p = SessionAttachedPayload(
            session_id="AGS-001", workspace_id="WS-001",
            binding_id="WSB-001", capabilities=["READ_WORKSPACE"],
            attached_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["capabilities"] == ["READ_WORKSPACE"]

    def test_package_streamed(self):
        p = PackageStreamedPayload(
            session_id="AGS-001", package_id="WSPKG-001",
            context_id="RTC-001", agent_id="AGNT-001",
            streamed_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["package_id"] == "WSPKG-001"

    def test_session_paused(self):
        p = SessionPausedPayload(
            session_id="AGS-001", workspace_id="WS-001", paused_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["session_id"] == "AGS-001"

    def test_session_resumed(self):
        p = SessionResumedPayload(
            session_id="AGS-001", workspace_id="WS-001", resumed_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["session_id"] == "AGS-001"

    def test_session_detached(self):
        p = SessionDetachedPayload(
            session_id="AGS-001", workspace_id="WS-001",
            binding_id="WSB-001", detached_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["binding_id"] == "WSB-001"

    def test_session_closed(self):
        p = SessionClosedPayload(
            session_id="AGS-001", workspace_id="WS-001",
            profile_id="AGNT-001", packages_streamed=5,
            events_emitted=10, closed_at=REF_TIME,
        )
        d = p.to_dict()
        assert d["packages_streamed"] == 5

    def test_all_payloads_frozen(self):
        payloads = [
            SessionCreatedPayload(session_id="AGS-001", profile_id="AGNT-001",
                                  workspace_id="WS-001", binding_id="WSB-001",
                                  created_at=REF_TIME),
            SessionAttachedPayload(session_id="AGS-001", workspace_id="WS-001",
                                   binding_id="WSB-001", attached_at=REF_TIME),
            PackageStreamedPayload(session_id="AGS-001", package_id="WSPKG-001",
                                   context_id="RTC-001", agent_id="AGNT-001",
                                   streamed_at=REF_TIME),
            SessionPausedPayload(session_id="AGS-001", workspace_id="WS-001",
                                 paused_at=REF_TIME),
            SessionResumedPayload(session_id="AGS-001", workspace_id="WS-001",
                                  resumed_at=REF_TIME),
            SessionDetachedPayload(session_id="AGS-001", workspace_id="WS-001",
                                   binding_id="WSB-001", detached_at=REF_TIME),
            SessionClosedPayload(session_id="AGS-001", workspace_id="WS-001",
                                 profile_id="AGNT-001", closed_at=REF_TIME),
        ]
        for p in payloads:
            with pytest.raises(AttributeError):
                p.session_id = "Hacked"
