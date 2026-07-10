"""Architecture conformance tests for the Task Tracker projection."""
from __future__ import annotations

import pytest
import datetime
import json
import logging
from unittest.mock import MagicMock
from typing import cast, Any
from uuid import uuid4

from rationalevault.projection_platform import (
    ConformanceSuite,
    ProjectionConformanceProvider,
    ProjectionContext,
    Projection,
)
from rationalevault.schema import EventRecord, EventType, EventMetadata

from ..events import TaskCreatedPayload
from ..projection import TaskTrackerProjection
from ..state import TaskTrackerState


# Decision:
# The Conformance Suite asserts architectural laws that must be obeyed
# by all projections (e.g., pure functions, idempotent state building, serializability).
#
# Why:
# It's easy for developers to accidentally slip I/O or non-serializable objects
# into a projection. Testing against the suite prevents infrastructure failures in CI.

class TaskTrackerProvider(ProjectionConformanceProvider):
    def create_projection(self) -> Projection:
        return TaskTrackerProjection()

    def events(self) -> list[EventRecord]:
        return [
            EventRecord(
                event_sequence=1,
                id=uuid4(),
                project_id=uuid4(),
                stream_id="test",
                version=1,
                event_type=cast(EventType, "TaskCreated"),
                metadata=EventMetadata(actor="test", source="test"),
                payload=TaskCreatedPayload(task_id="1", description="A", owner="B").to_dict(),
                parent_id=None,
                recorded_at=datetime.datetime.now(datetime.timezone.utc)
            )
        ]

    def edge_case_events(self) -> list[list[EventRecord]]:
        return [[], self.events()]

    def snapshot_points(self, events: list[EventRecord]) -> list[int]:
        return [0, len(events)]

    def supported_events(self) -> list[EventRecord]:
        return self.events()

    def unsupported_events(self) -> list[EventRecord]:
        return []

    def state_equal(self, a: Any, b: Any) -> bool:
        return a == b

    def canonical_json(self, payload: dict) -> str:
        return json.dumps(payload, sort_keys=True)

    def create_context(self, projection: Projection) -> ProjectionContext:
        from rationalevault.projection_platform import DependencyReader, MetricsCollector
        return ProjectionContext(
            projection_id="task_tracker",
            event_store=MagicMock(),
            snapshot_manager=MagicMock(),
            dependency_reader=DependencyReader(),
            logger=logging.getLogger("test"),
            metrics=MetricsCollector()
        )


class TestTaskTrackerConformance:
    """Run the standard conformance suite against the TaskTracker projection."""

    def test_conformance_suite(self):
        projection = TaskTrackerProjection()
        provider = TaskTrackerProvider()
        suite = ConformanceSuite(projection, provider)
        report = suite.run()
        
        failed = {name: result.message for name, result in report.law_results.items() if not result.passed}
        assert not failed, f"Conformance laws failed: {failed}"
