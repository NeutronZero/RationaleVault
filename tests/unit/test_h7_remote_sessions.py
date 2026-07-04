"""
H7 — Remote Sessions Tests.

RuntimeNode, NodeHealth, RemoteSession, SessionHandoff, NodeRegistry,
CrossNodeTelemetry, AggregationStrategy, NodeTelemetryAggregator.
"""
from __future__ import annotations

import pytest
from typing import Any

from rationalevault.runtime.remote_models import (
    HandoffStatus,
    HandoffType,
    NodeHealth,
    NodeRegistry,
    NodeStatus,
    RemoteSession,
    RemoteSessionStatus,
    RuntimeNode,
    SessionHandoff,
)
from rationalevault.runtime.remote_events import (
    CrossNodeTelemetryAggregatedPayload,
    NodeRegisteredPayload,
    NodeStatusChangedPayload,
    SessionHandoffFailedPayload,
    SessionMigratedPayload,
    SessionMigratingPayload,
)
from rationalevault.runtime.telemetry_aggregator import (
    AggregationMethod,
    AverageAggregation,
    CrossNodeTelemetry,
    MaxAggregation,
    MinAggregation,
    NodeTelemetryAggregator,
    P95Aggregation,
    SumAggregation,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_node(name: str = "node-1", endpoint: str = "http://localhost:8001") -> RuntimeNode:
    return RuntimeNode(
        node_id=RuntimeNode.generate_node_id(name, endpoint),
        name=name,
        transport_type="MCP",
        endpoint=endpoint,
        workspace_ids=["WS-1"],
    )


def _make_health(
    node_id: str = "RSES-NODE-TEST",
    status: NodeStatus = NodeStatus.ONLINE,
    load: float = 0.5,
) -> NodeHealth:
    return NodeHealth(
        node_id=node_id,
        status=status,
        load=load,
        active_sessions=3,
    )


def _make_remote_session(
    logical_session_id: str = "AGS-1",
    node_id: str = "RSES-NODE-1",
) -> RemoteSession:
    return RemoteSession(
        remote_session_id=RemoteSession.generate_remote_session_id(
            logical_session_id, node_id,
        ),
        logical_session_id=logical_session_id,
        agent_id="AGNT-1",
        workspace_id="WS-1",
        current_node_id=node_id,
    )


def _make_handoff(
    remote_session_id: str = "RSES-RS-1",
    source: str = "RSES-NODE-1",
    target: str = "RSES-NODE-2",
) -> SessionHandoff:
    return SessionHandoff(
        handoff_id=SessionHandoff.generate_handoff_id(
            remote_session_id, source, target,
        ),
        remote_session_id=remote_session_id,
        source_node_id=source,
        target_node_id=target,
    )


# ── RuntimeNode ───────────────────────────────────────────────────────────

class TestRuntimeNode:
    def test_frozen(self):
        node = _make_node()
        with pytest.raises(AttributeError):
            node.name = "hacked"

    def test_to_dict(self):
        node = _make_node(name="worker-1", endpoint="http://host:9000")
        d = node.to_dict()
        assert d["name"] == "worker-1"
        assert d["transport_type"] == "MCP"
        assert d["endpoint"] == "http://host:9000"

    def test_generate_id_deterministic(self):
        id1 = RuntimeNode.generate_node_id("n", "http://x:1")
        id2 = RuntimeNode.generate_node_id("n", "http://x:1")
        assert id1 == id2
        assert id1.startswith("RSES-NODE-")

    def test_capabilities(self):
        node = RuntimeNode(
            node_id="N1", name="n", transport_type="MCP",
            endpoint="http://x:1",
            capabilities=frozenset({"CAN_HOST_REMOTE", "CAN_MIGRATE"}),
        )
        assert "CAN_HOST_REMOTE" in node.capabilities


# ── NodeHealth ────────────────────────────────────────────────────────────

class TestNodeHealth:
    def test_to_dict(self):
        h = _make_health(node_id="N1", status=NodeStatus.DRAINING, load=0.8)
        d = h.to_dict()
        assert d["node_id"] == "N1"
        assert d["status"] == "DRAINING"
        assert d["load"] == 0.8
        assert d["active_sessions"] == 3

    def test_default_status(self):
        h = NodeHealth(node_id="N1")
        assert h.status == NodeStatus.ONLINE
        assert h.load == 0.0


# ── RemoteSession ─────────────────────────────────────────────────────────

class TestRemoteSession:
    def test_frozen(self):
        rs = _make_remote_session()
        with pytest.raises(AttributeError):
            rs.current_node_id = "hacked"

    def test_to_dict(self):
        rs = _make_remote_session(logical_session_id="AGS-42", node_id="N-1")
        d = rs.to_dict()
        assert d["logical_session_id"] == "AGS-42"
        assert d["current_node_id"] == "N-1"
        assert d["status"] == "ACTIVE"

    def test_generate_id_deterministic(self):
        id1 = RemoteSession.generate_remote_session_id("AGS-1", "N1")
        id2 = RemoteSession.generate_remote_session_id("AGS-1", "N1")
        assert id1 == id2
        assert id1.startswith("RSES-RS-")

    def test_handoff_count(self):
        rs = _make_remote_session()
        assert rs.handoff_count == 0


# ── SessionHandoff ────────────────────────────────────────────────────────

class TestSessionHandoff:
    def test_frozen(self):
        ho = _make_handoff()
        with pytest.raises(AttributeError):
            ho.status = HandoffStatus.COMPLETED

    def test_to_dict(self):
        ho = _make_handoff(source="N1", target="N2")
        d = ho.to_dict()
        assert d["source_node_id"] == "N1"
        assert d["target_node_id"] == "N2"
        assert d["status"] == "INITIATED"
        assert d["handoff_type"] == "MIGRATION"

    def test_generate_id_deterministic(self):
        id1 = SessionHandoff.generate_handoff_id("RS-1", "N1", "N2")
        id2 = SessionHandoff.generate_handoff_id("RS-1", "N1", "N2")
        assert id1 == id2
        assert id1.startswith("RSES-HO-")

    def test_state_machine(self):
        ho = _make_handoff()
        assert ho.status == HandoffStatus.INITIATED
        # State transitions are represented by new records
        completed = SessionHandoff(
            handoff_id=ho.handoff_id,
            remote_session_id=ho.remote_session_id,
            source_node_id=ho.source_node_id,
            target_node_id=ho.target_node_id,
            status=HandoffStatus.COMPLETED,
            completed_at="2026-01-01T00:00:00Z",
        )
        assert completed.status == HandoffStatus.COMPLETED


# ── NodeRegistry ──────────────────────────────────────────────────────────

class TestNodeRegistry:
    def test_initial_state(self):
        reg = NodeRegistry()
        assert reg.node_count == 0
        assert reg.online_count == 0

    def test_add_node(self):
        reg = NodeRegistry()
        node = _make_node()
        health = _make_health(node_id=node.node_id)
        new_reg = reg.add_node(node, health)
        assert new_reg.node_count == 1
        assert new_reg.online_count == 1
        assert reg.node_count == 0  # Original unchanged

    def test_add_node_without_health(self):
        reg = NodeRegistry()
        node = _make_node()
        new_reg = reg.add_node(node)
        assert new_reg.node_count == 1
        assert new_reg.online_count == 0  # No health = not online

    def test_update_node(self):
        node = _make_node()
        reg = NodeRegistry(nodes=(node,))
        updated = RuntimeNode(
            node_id=node.node_id,
            name="updated",
            transport_type="REST",
            endpoint="http://new:9000",
        )
        new_reg = reg.update_node(updated)
        assert new_reg.get_node(node.node_id).name == "updated"

    def test_update_health(self):
        node = _make_node()
        health = _make_health(node_id=node.node_id, status=NodeStatus.ONLINE)
        reg = NodeRegistry(nodes=(node,), health=(health,))
        new_health = NodeHealth(
            node_id=node.node_id, status=NodeStatus.DRAINING, load=0.9,
        )
        new_reg = reg.update_health(new_health)
        assert new_reg.get_health(node.node_id).status == NodeStatus.DRAINING

    def test_remove_node(self):
        node = _make_node()
        health = _make_health(node_id=node.node_id)
        reg = NodeRegistry(nodes=(node,), health=(health,))
        new_reg = reg.remove_node(node.node_id)
        assert new_reg.node_count == 0
        assert len(new_reg.health) == 0

    def test_get_nodes_for_workspace(self):
        n1 = _make_node(name="n1")
        n2 = RuntimeNode(
            node_id="N2", name="n2", transport_type="REST",
            endpoint="http://x:2", workspace_ids=["WS-2"],
        )
        reg = NodeRegistry(nodes=(n1, n2))
        result = reg.get_nodes_for_workspace("WS-1")
        assert len(result) == 1
        assert result[0].node_id == n1.node_id

    def test_online_nodes(self):
        n1 = _make_node(name="n1")
        n2 = _make_node(name="n2")
        h1 = _make_health(node_id=n1.node_id, status=NodeStatus.ONLINE)
        h2 = _make_health(node_id=n2.node_id, status=NodeStatus.OFFLINE)
        reg = NodeRegistry(nodes=(n1, n2), health=(h1, h2))
        assert reg.online_count == 1
        assert reg.online_nodes[0].node_id == n1.node_id

    def test_to_dict(self):
        node = _make_node()
        health = _make_health(node_id=node.node_id)
        reg = NodeRegistry(nodes=(node,), health=(health,))
        d = reg.to_dict()
        assert d["node_count"] == 1
        assert d["online_count"] == 1
        assert len(d["nodes"]) == 1

    def test_immutability(self):
        node = _make_node()
        reg = NodeRegistry()
        new_reg = reg.add_node(node)
        assert reg.node_count == 0
        assert new_reg.node_count == 1


# ── CrossNodeTelemetry ────────────────────────────────────────────────────

class TestCrossNodeTelemetry:
    def test_frozen(self):
        ct = CrossNodeTelemetry(
            aggregation_id="RSES-XTEL-1",
            source_node_ids=["N1"],
            metric_type="RETRIEVAL_PRECISION",
            value=0.75,
            sample_count=10,
            aggregation_method="AVERAGE",
        )
        with pytest.raises(AttributeError):
            ct.value = 0.0

    def test_to_dict(self):
        ct = CrossNodeTelemetry(
            aggregation_id="RSES-XTEL-1",
            source_node_ids=["N1", "N2"],
            metric_type="CACHE_HIT_RATE",
            value=0.6,
            sample_count=20,
            aggregation_method="AVERAGE",
        )
        d = ct.to_dict()
        assert d["metric_type"] == "CACHE_HIT_RATE"
        assert d["value"] == 0.6
        assert d["source_node_ids"] == ["N1", "N2"]

    def test_generate_id_deterministic(self):
        id1 = CrossNodeTelemetry.generate_aggregation_id("PRECISION", "AVG", "123")
        id2 = CrossNodeTelemetry.generate_aggregation_id("PRECISION", "AVG", "123")
        assert id1 == id2
        assert id1.startswith("RSES-XTEL-")


# ── Aggregation Strategies ────────────────────────────────────────────────

class TestAggregationStrategies:
    def test_average(self):
        s = AverageAggregation()
        assert s.method_name == "AVERAGE"
        assert s.aggregate([1.0, 2.0, 3.0]) == 2.0

    def test_average_empty(self):
        assert AverageAggregation().aggregate([]) == 0.0

    def test_sum(self):
        s = SumAggregation()
        assert s.method_name == "SUM"
        assert s.aggregate([1.0, 2.0, 3.0]) == 6.0

    def test_min(self):
        s = MinAggregation()
        assert s.method_name == "MIN"
        assert s.aggregate([3.0, 1.0, 2.0]) == 1.0

    def test_max(self):
        s = MaxAggregation()
        assert s.method_name == "MAX"
        assert s.aggregate([1.0, 3.0, 2.0]) == 3.0

    def test_p95(self):
        s = P95Aggregation()
        assert s.method_name == "P95"
        values = list(range(1, 101))  # 1..100
        result = s.aggregate([float(v) for v in values])
        assert result == 95.0


# ── NodeTelemetryAggregator ───────────────────────────────────────────────

class TestNodeTelemetryAggregator:
    def test_initial_state(self):
        agg = NodeTelemetryAggregator()
        assert len(agg.strategies) == 5

    def test_aggregate_single_node(self):
        agg = NodeTelemetryAggregator()
        node_telemetry = {
            "N1": [("RETRIEVAL_PRECISION", 0.6), ("RETRIEVAL_PRECISION", 0.8)],
        }
        result = agg.aggregate(node_telemetry, "RETRIEVAL_PRECISION")
        assert result.value == 0.7
        assert result.sample_count == 2
        assert result.source_node_ids == ["N1"]

    def test_aggregate_multi_node(self):
        agg = NodeTelemetryAggregator()
        node_telemetry = {
            "N1": [("RETRIEVAL_PRECISION", 0.6)],
            "N2": [("RETRIEVAL_PRECISION", 0.8)],
            "N3": [("RETRIEVAL_PRECISION", 0.7)],
        }
        result = agg.aggregate(node_telemetry, "RETRIEVAL_PRECISION")
        assert abs(result.value - 0.7) < 0.01
        assert result.sample_count == 3
        assert len(result.source_node_ids) == 3

    def test_aggregate_different_methods(self):
        agg = NodeTelemetryAggregator()
        node_telemetry = {
            "N1": [("LATENCY", 100.0)],
            "N2": [("LATENCY", 200.0)],
            "N3": [("LATENCY", 300.0)],
        }
        avg = agg.aggregate(node_telemetry, "LATENCY", "AVERAGE")
        assert avg.value == 200.0

        total = agg.aggregate(node_telemetry, "LATENCY", "SUM")
        assert total.value == 600.0

        minimum = agg.aggregate(node_telemetry, "LATENCY", "MIN")
        assert minimum.value == 100.0

        maximum = agg.aggregate(node_telemetry, "LATENCY", "MAX")
        assert maximum.value == 300.0

    def test_aggregate_empty(self):
        agg = NodeTelemetryAggregator()
        result = agg.aggregate({}, "RETRIEVAL_PRECISION")
        assert result.value == 0.0
        assert result.sample_count == 0
        assert len(result.source_node_ids) == 0

    def test_aggregate_unknown_method_falls_back(self):
        agg = NodeTelemetryAggregator()
        node_telemetry = {"N1": [("X", 1.0), ("X", 2.0)]}
        result = agg.aggregate(node_telemetry, "X", "UNKNOWN")
        assert result.aggregation_method == "AVERAGE"
        assert result.value == 1.5

    def test_aggregate_all(self):
        agg = NodeTelemetryAggregator()
        node_telemetry = {
            "N1": [("PRECISION", 0.6), ("LATENCY", 100.0)],
            "N2": [("PRECISION", 0.8), ("LATENCY", 200.0)],
        }
        results = agg.aggregate_all(node_telemetry)
        assert len(results) == 2
        metric_types = {r.metric_type for r in results}
        assert "PRECISION" in metric_types
        assert "LATENCY" in metric_types

    def test_aggregate_deterministic(self):
        agg = NodeTelemetryAggregator()
        node_telemetry = {"N1": [("X", 0.5)], "N2": [("X", 0.7)]}
        r1 = agg.aggregate(node_telemetry, "X")
        r2 = agg.aggregate(node_telemetry, "X")
        assert r1.value == r2.value
        assert r1.sample_count == r2.sample_count


# ── Event Payloads ────────────────────────────────────────────────────────

class TestRemoteEvents:
    def test_node_registered_payload(self):
        p = NodeRegisteredPayload(
            node_id="N1", name="worker", transport_type="MCP",
            endpoint="http://x:1", registered_at="2026-01-01",
        )
        d = p.to_dict()
        assert d["node_id"] == "N1"
        assert d["name"] == "worker"

    def test_node_status_changed_payload(self):
        p = NodeStatusChangedPayload(
            node_id="N1", old_status="ONLINE", new_status="DRAINING",
        )
        d = p.to_dict()
        assert d["old_status"] == "ONLINE"
        assert d["new_status"] == "DRAINING"

    def test_session_migrating_payload(self):
        p = SessionMigratingPayload(
            remote_session_id="RS-1", logical_session_id="AGS-1",
            source_node_id="N1", target_node_id="N2",
            handoff_id="HO-1", handoff_type="MIGRATION",
        )
        d = p.to_dict()
        assert d["source_node_id"] == "N1"
        assert d["target_node_id"] == "N2"

    def test_session_migrated_payload(self):
        p = SessionMigratedPayload(
            remote_session_id="RS-1", logical_session_id="AGS-1",
            target_node_id="N2", handoff_id="HO-1",
            packages_transferred=5, events_transferred=12,
        )
        d = p.to_dict()
        assert d["packages_transferred"] == 5
        assert d["events_transferred"] == 12

    def test_session_handoff_failed_payload(self):
        p = SessionHandoffFailedPayload(
            remote_session_id="RS-1", source_node_id="N1",
            target_node_id="N2", handoff_id="HO-1",
            reason="Target unreachable",
        )
        d = p.to_dict()
        assert d["reason"] == "Target unreachable"

    def test_cross_node_telemetry_aggregated_payload(self):
        p = CrossNodeTelemetryAggregatedPayload(
            aggregation_id="XTEL-1", source_node_ids=["N1", "N2"],
            metric_type="PRECISION", aggregation_method="AVERAGE",
            value=0.7, sample_count=10,
        )
        d = p.to_dict()
        assert d["value"] == 0.7
        assert d["sample_count"] == 10


# ── Integration ───────────────────────────────────────────────────────────

class TestRemoteSessionsIntegration:
    def test_multi_node_workspace_sharing(self):
        """Multiple nodes share a workspace."""
        n1 = _make_node(name="node-1")
        n2 = _make_node(name="node-2", endpoint="http://localhost:8002")
        h1 = _make_health(node_id=n1.node_id, status=NodeStatus.ONLINE)
        h2 = _make_health(node_id=n2.node_id, status=NodeStatus.ONLINE)

        reg = NodeRegistry()
        reg = reg.add_node(n1, h1)
        reg = reg.add_node(n2, h2)

        assert reg.node_count == 2
        assert reg.online_count == 2
        ws_nodes = reg.get_nodes_for_workspace("WS-1")
        assert len(ws_nodes) == 2

    def test_agent_migration_flow(self):
        """Agent migrates from Node A to Node B."""
        n1 = _make_node(name="source")
        n2 = _make_node(name="target", endpoint="http://localhost:8002")

        # Create remote session on source
        rs = _make_remote_session(node_id=n1.node_id)
        assert rs.current_node_id == n1.node_id
        assert rs.status == RemoteSessionStatus.ACTIVE

        # Initiate handoff
        ho = _make_handoff(
            remote_session_id=rs.remote_session_id,
            source=n1.node_id,
            target=n2.node_id,
        )
        assert ho.status == HandoffStatus.INITIATED

        # Complete handoff (new record)
        completed = SessionHandoff(
            handoff_id=ho.handoff_id,
            remote_session_id=ho.remote_session_id,
            source_node_id=ho.source_node_id,
            target_node_id=ho.target_node_id,
            status=HandoffStatus.COMPLETED,
            packages_transferred=3,
            events_transferred=8,
            completed_at="2026-01-01T00:01:00Z",
        )
        assert completed.status == HandoffStatus.COMPLETED
        assert completed.packages_transferred == 3

    def test_telemetry_aggregation_across_nodes(self):
        """Telemetry from multiple nodes is aggregated."""
        agg = NodeTelemetryAggregator()
        node_telemetry = {
            "N1": [("RETRIEVAL_PRECISION", 0.6), ("CACHE_HIT_RATE", 0.5)],
            "N2": [("RETRIEVAL_PRECISION", 0.8), ("CACHE_HIT_RATE", 0.7)],
            "N3": [("RETRIEVAL_PRECISION", 0.7)],
        }
        results = agg.aggregate_all(node_telemetry)
        assert len(results) == 2

        precision = [r for r in results if r.metric_type == "RETRIEVAL_PRECISION"][0]
        assert precision.sample_count == 3
        assert len(precision.source_node_ids) == 3
        assert abs(precision.value - 0.7) < 0.01
