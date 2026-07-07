"""Conformance tests for GovernanceProjection."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from rationalevault.db.sqlite_store import SQLiteEventStore
from rationalevault.projection_platform.conformance import ConformanceSuite
from rationalevault.projection_platform.context import (
    DependencyReader,
    MetricsCollector,
    ProjectionContext,
)
from rationalevault.cognitive_head.snapshot import NullSnapshotManager
from rationalevault.governance.projection import GovernanceProjection
from rationalevault.governance.state import GovernanceState
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


def _event(
    event_type: EventType,
    payload: dict,
    seq: int = 1,
    project_id=None,
) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid4(),
        project_id=project_id or uuid4(),
        stream_id="main",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


class GovernanceConformanceProvider:
    """ProjectionConformanceProvider for GovernanceProjection."""

    def __init__(self, tmp_path=None) -> None:
        self._tmp_path = tmp_path
        self._pid = uuid4()

    def create_projection(self) -> GovernanceProjection:
        return GovernanceProjection()

    def events(self) -> list[EventRecord]:
        pid = self._pid
        return [
            _event(EventType.GOVERNANCE_RULE_CREATED, {
                "metadata": {
                    "id": "policy_1",
                    "version": 1,
                    "description": "Block critical risk",
                    "severity": "critical",
                    "action": "block",
                },
                "condition": {
                    "categories": ["risk"],
                    "minimum_priority": 0.8,
                },
            }, 1, pid),
            _event(EventType.GOVERNANCE_RULE_UPDATED, {
                "metadata": {
                    "id": "policy_1",
                    "version": 1,
                    "description": "Block critical risk updated",
                    "severity": "critical",
                    "action": "block",
                },
                "condition": {
                    "categories": ["risk"],
                    "minimum_priority": 0.7,
                },
            }, 2, pid),
            _event(EventType.GOVERNANCE_RULE_CREATED, {
                "metadata": {
                    "id": "policy_2",
                    "version": 1,
                    "description": "Notify follow_up",
                    "severity": "info",
                    "action": "notify",
                },
                "condition": {
                    "categories": ["follow_up"],
                },
            }, 3, pid),
            _event(EventType.GOVERNANCE_RULE_DELETED, {
                "rule_id": "policy_2",
                "version": 1,
            }, 4, pid),
        ]

    def edge_case_events(self) -> list[list[EventRecord]]:
        pid = self._pid
        return [
            [_event(EventType.GOVERNANCE_RULE_CREATED, {
                "metadata": {
                    "id": "single",
                    "version": 1,
                    "severity": "warning",
                    "action": "log",
                },
            }, 1, pid)],
            [],
        ]

    def snapshot_points(self, events: list[EventRecord]) -> list[int]:
        n = len(events)
        if n < 4:
            return [0, n]
        return [0, n // 2, n]

    def supported_events(self) -> list[EventRecord]:
        consumed = GovernanceProjection().metadata.consumed_events.types
        return [e for e in self.events() if e.event_type in consumed]

    def unsupported_events(self) -> list[EventRecord]:
        pid = self._pid
        return [
            _event(EventType.TASK_COMPLETED, {
                "task_id": "t1",
            }, 200, pid),
        ]

    def state_equal(self, a: Any, b: Any) -> bool:
        if not isinstance(a, GovernanceState) or not isinstance(b, GovernanceState):
            return a == b

        if len(a.rules) != len(b.rules):
            return False

        for ar, br in zip(a.rules, b.rules, strict=True):
            if ar.metadata.id != br.metadata.id:
                return False
            if ar.metadata.version != br.metadata.version:
                return False
            if ar.metadata.description != br.metadata.description:
                return False
            if ar.metadata.severity != br.metadata.severity:
                return False
            if ar.metadata.action != br.metadata.action:
                return False
            if ar.condition.categories != br.condition.categories:
                return False
            if ar.condition.minimum_priority != br.condition.minimum_priority:
                return False
            if ar.condition.severities != br.condition.severities:
                return False
            if ar.enabled != br.enabled:
                return False

        return True

    def canonical_json(self, payload: dict) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def create_context(self, projection: GovernanceProjection) -> ProjectionContext:
        return ProjectionContext(
            projection_id="governance",
            event_store=SQLiteEventStore()
            if self._tmp_path is None
            else SQLiteEventStore(db_path=str(self._tmp_path / "ctx.db")),
            snapshot_manager=NullSnapshotManager(),
            dependency_reader=DependencyReader(),
            logger=__import__("logging").getLogger("conformance"),
            metrics=MetricsCollector(),
        )


class TestGovernanceConformance:
    """Run the full Conformance Suite against GovernanceProjection."""

    def test_all_laws_pass(self):
        provider = GovernanceConformanceProvider()
        projection = provider.create_projection()
        suite = ConformanceSuite(projection, provider)
        report = suite.run()
        assert report.all_passed, f"Failed laws: {report.failed_laws}"
