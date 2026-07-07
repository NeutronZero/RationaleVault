"""ProjectionCompiler — compiles a single projection using the platform."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from rationalevault.projection_platform.context import (
    DependencyReader,
    MetricsCollector,
    ProjectionContext,
)
from rationalevault.projection_platform.models import ProjectionHealth
from rationalevault.projection_platform.protocols import Projection
from rationalevault.projection_platform.registry import ProjectionRegistry
from rationalevault.cognitive_head.snapshot import (
    NullSnapshotManager,
    SNAPSHOT_SERIALIZERS,
    SnapshotManager,
)
from rationalevault.cognitive_head.snapshot_payload import (
    ProjectionSnapshotPayload,
)
from rationalevault.db.event_store import EventStore


class ProjectionCompiler:
    """Compiles projections using the platform infrastructure.

    Owns the replay strategy (full, delta, fast path) for any projection.
    Projections are pure — the compiler handles I/O, snapshots, and telemetry.
    """

    def __init__(
        self,
        event_store: Optional[EventStore] = None,
        snapshot_manager: Optional[SnapshotManager] = None,
        registry: Optional[ProjectionRegistry] = None,
    ) -> None:
        self._event_store = event_store or EventStore()
        self._snapshot_manager = snapshot_manager or NullSnapshotManager()
        self._registry = registry or ProjectionRegistry()
        self._dependency_reader = DependencyReader()
        self._health: dict[str, ProjectionHealth] = {}

    @property
    def registry(self) -> ProjectionRegistry:
        return self._registry

    def compile(
        self,
        project_id: UUID,
        projection_id: str,
    ) -> Any:
        """Compile a single projection, returning its state.

        Replay strategy:
        1. Load valid snapshot → fast path (no new events)
        2. Load snapshot + delta events → delta replay
        3. No snapshot → full replay
        """
        projection = self._registry.get(projection_id)
        meta = projection.metadata

        self._health[projection_id] = ProjectionHealth.BUILDING

        try:
            # Resolve dependencies first
            for dep in meta.dependencies:
                if dep.projection_id not in self._health:
                    self.compile(project_id, dep.projection_id)

            # Load snapshot
            snapshot_result = self._snapshot_manager.load_valid_snapshot(
                project_id, projection_id,
            )
            snapshot_payload: Optional[ProjectionSnapshotPayload] = None
            snapshot_seq = 0

            if snapshot_result.valid and snapshot_result.payload is not None:
                snapshot_payload = snapshot_result.payload
                snapshot_seq = snapshot_payload.sequence

            # Get latest sequence
            latest_seq = self._event_store.get_latest_sequence(project_id)

            # Fast path: snapshot is current
            if snapshot_seq >= latest_seq and snapshot_payload is not None:
                state = projection.deserialize(snapshot_payload.to_dict())
                self._health[projection_id] = ProjectionHealth.READY
                return state

            # Get events since snapshot
            if snapshot_seq > 0:
                events = self._event_store.get_events_since(
                    project_id, snapshot_seq,
                )
            else:
                events = self._event_store.get_project_stream(project_id)

            # Build initial state from snapshot
            initial_state = None
            if snapshot_payload is not None:
                initial_state = projection.deserialize(
                    snapshot_payload.to_dict(),
                )

            # Reduce
            state = projection.reduce(events, initial_state=initial_state)

            # Save snapshot if applicable
            if meta.capabilities.snapshotable:
                self._save_snapshot(
                    project_id, projection_id, projection, state, latest_seq,
                )

            self._health[projection_id] = ProjectionHealth.READY
            return state

        except Exception:
            self._health[projection_id] = ProjectionHealth.FAILED
            raise

    def compile_all(self, project_id: UUID) -> dict[str, Any]:
        """Compile all registered projections in dependency order."""
        results: dict[str, Any] = {}
        for projection in self._registry.all():
            meta = projection.metadata
            results[meta.id] = self.compile(project_id, meta.id)
        return results

    def health(self, projection_id: str) -> ProjectionHealth:
        return self._health.get(projection_id, ProjectionHealth.UNKNOWN)

    def _build_context(self, projection_id: str) -> ProjectionContext:
        return ProjectionContext(
            projection_id=projection_id,
            event_store=self._event_store,
            snapshot_manager=self._snapshot_manager,
            dependency_reader=self._dependency_reader,
            logger=__import__("logging").getLogger(
                f"projection.{projection_id}"
            ),
            metrics=MetricsCollector(),
        )

    def _save_snapshot(
        self,
        project_id: UUID,
        projection_id: str,
        projection: Projection,
        state: Any,
        current_seq: int,
    ) -> None:
        """Save a snapshot if the serializer is registered."""
        if projection_id not in SNAPSHOT_SERIALIZERS:
            return

        try:
            serializer_cls = SNAPSHOT_SERIALIZERS[projection_id]
            state_dict = projection.serialize(state)
            payload = serializer_cls.from_dict(state_dict)
            self._snapshot_manager.refresh_snapshot(
                project_id, projection_id, payload, current_seq,
            )
        except Exception:
            pass  # Snapshot save is best-effort
