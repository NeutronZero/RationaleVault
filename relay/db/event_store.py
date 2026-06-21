"""
Relay Event Store — Immutable append-only ledger backed by PostgreSQL.

Design guarantees:
  - event_sequence (BIGSERIAL) is the ONLY authoritative replay ordering key.
    All reads use ORDER BY event_sequence ASC. Never ORDER BY version or recorded_at.

  - Per-project version monotonicity is enforced via PostgreSQL advisory locks
    (pg_advisory_xact_lock). This prevents version collisions in concurrent
    multi-agent writes without requiring application-level serialization.

  - The UNIQUE (project_id, version) constraint acts as a concurrency guard.
    It will raise IntegrityError if the advisory lock somehow fails — this is
    a safety net, not the primary mechanism.

  - EventStore is fully synchronous (psycopg3). No async complexity in V1.

  - All methods accept an optional `conn` parameter. If omitted, a fresh
    connection is opened and auto-committed. Pass an existing connection when
    you need multiple appends in a single transaction.

API:
    append_event(project_id, stream_id, event_type, payload, metadata, ...)
        → EventRecord

    get_project_stream(project_id, since_sequence=0)
        → list[EventRecord]   (ORDER BY event_sequence ASC)

    replay_stream(project_id, since_sequence=0)
        → Iterator[EventRecord]   (yields one at a time)

    get_stream(project_id, stream_id, since_sequence=0)
        → list[EventRecord]   (filtered to one sub-stream)

    get_event_count(project_id)
        → int
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Iterator, Optional
from uuid import UUID

import psycopg

from relay.db.connection import get_connection
from relay.schema.events import EventMetadata, EventRecord, EventType


class EventStore:
    """
    Append-only event ledger backed by PostgreSQL.

    Instantiate once; reuse across calls. Thread-safe for read operations.
    Write operations use advisory locks and are safe under concurrent access.
    """

    # ── Write ──────────────────────────────────────────────────────────────

    def append_event(
        self,
        project_id: UUID,
        stream_id: str,
        event_type: EventType,
        payload: dict[str, Any],
        metadata: EventMetadata,
        parent_id: Optional[UUID] = None,
        conn: Optional[psycopg.Connection] = None,
    ) -> EventRecord:
        """
        Append a single event to the ledger.

        Steps:
          1. Acquire a per-project PostgreSQL advisory lock (scoped to transaction).
          2. Read MAX(version) for this project and compute next_version.
          3. Insert the event row. PostgreSQL assigns event_sequence (BIGSERIAL).
          4. Return a fully hydrated EventRecord.

        The advisory lock key is derived from the project_id UUID to provide
        per-project serialization without blocking unrelated projects.

        Args:
            project_id:  UUID of the project this event belongs to.
            stream_id:   Logical sub-stream grouping (e.g. "main", "tasks").
            event_type:  What happened.
            payload:     Event-specific data.
            metadata:    Structured envelope: actor, source, correlation_id, session_id.
            parent_id:   Optional UUID of the causing event.
            conn:        Optional existing connection (for multi-event transactions).

        Returns:
            EventRecord with event_sequence, id, and recorded_at filled in.
        """
        def _run(c: psycopg.Connection) -> EventRecord:
            with c.cursor() as cur:
                # Advisory lock scoped to this transaction, keyed by project_id.
                # Prevents version collisions from concurrent writers for the same project.
                lock_key = UUID(str(project_id)).int & 0x7FFFFFFFFFFFFFFF
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))

                # Compute next per-project version
                cur.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 AS next_version "
                    "FROM relay_events WHERE project_id = %s",
                    (str(project_id),),
                )
                next_version: int = cur.fetchone()["next_version"]

                event_id = uuid.uuid4()

                cur.execute(
                    """
                    INSERT INTO relay_events (
                        id, project_id, stream_id, version,
                        event_type, metadata, payload, parent_id
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s::jsonb, %s::jsonb, %s
                    )
                    RETURNING event_sequence, recorded_at
                    """,
                    (
                        str(event_id),
                        str(project_id),
                        stream_id,
                        next_version,
                        event_type.value,
                        json.dumps(metadata.to_dict()),
                        json.dumps(payload),
                        str(parent_id) if parent_id else None,
                    ),
                )
                result = cur.fetchone()

            return EventRecord(
                event_sequence=result["event_sequence"],
                id=event_id,
                project_id=project_id,
                stream_id=stream_id,
                version=next_version,
                event_type=event_type,
                metadata=metadata,
                payload=payload,
                parent_id=parent_id,
                recorded_at=result["recorded_at"],
            )

        if conn is not None:
            return _run(conn)
        with get_connection() as c:
            return _run(c)

    # ── Read ───────────────────────────────────────────────────────────────

    def get_project_stream(
        self,
        project_id: UUID,
        since_sequence: int = 0,
    ) -> list[EventRecord]:
        """
        Return all events for a project ordered by event_sequence ASC.

        This is the primary method used by compile_cognitive_head().
        Always loads the full stream (or events after since_sequence).

        Args:
            project_id:      The project to load.
            since_sequence:  Only return events with event_sequence > this value.
                             Used for incremental loads (future snapshot integration).
        """
        sql = """
            SELECT event_sequence, id, project_id, stream_id, version,
                   event_type, metadata, payload, parent_id, recorded_at
            FROM relay_events
            WHERE project_id = %s
              AND event_sequence > %s
            ORDER BY event_sequence ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(project_id), since_sequence))
                return [self._row_to_record(row) for row in cur.fetchall()]

    def replay_stream(
        self,
        project_id: UUID,
        since_sequence: int = 0,
    ) -> Iterator[EventRecord]:
        """
        Generator that yields events one at a time in event_sequence order.

        Prefer this over get_project_stream() for very large streams where
        loading all events into memory is undesirable. In V1 the volumes
        are small enough that get_project_stream() is fine for most uses.
        """
        sql = """
            SELECT event_sequence, id, project_id, stream_id, version,
                   event_type, metadata, payload, parent_id, recorded_at
            FROM relay_events
            WHERE project_id = %s
              AND event_sequence > %s
            ORDER BY event_sequence ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(project_id), since_sequence))
                for row in cur:
                    yield self._row_to_record(row)

    def get_stream(
        self,
        project_id: UUID,
        stream_id: str,
        since_sequence: int = 0,
    ) -> list[EventRecord]:
        """
        Return events for a specific sub-stream within a project.

        Still ordered by event_sequence ASC globally — not by stream position.
        Use this for targeted queries (e.g. only "decisions" events).

        Note: compile_cognitive_head() loads ALL streams. Use this only for
        debugging or targeted analysis, not for compilation.
        """
        sql = """
            SELECT event_sequence, id, project_id, stream_id, version,
                   event_type, metadata, payload, parent_id, recorded_at
            FROM relay_events
            WHERE project_id = %s
              AND stream_id = %s
              AND event_sequence > %s
            ORDER BY event_sequence ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(project_id), stream_id, since_sequence))
                return [self._row_to_record(row) for row in cur.fetchall()]

    def get_event_count(self, project_id: UUID) -> int:
        """Return the total number of events recorded for a project."""
        sql = "SELECT COUNT(*) AS cnt FROM relay_events WHERE project_id = %s"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(project_id),))
                return cur.fetchone()["cnt"]

    # ── Internal ───────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_record(row: dict) -> EventRecord:
        """Convert a raw database row (dict) to a typed EventRecord."""
        raw_metadata = row["metadata"]
        if isinstance(raw_metadata, str):
            raw_metadata = json.loads(raw_metadata)

        raw_payload = row["payload"]
        if isinstance(raw_payload, str):
            raw_payload = json.loads(raw_payload)

        return EventRecord(
            event_sequence=row["event_sequence"],
            id=UUID(str(row["id"])),
            project_id=UUID(str(row["project_id"])),
            stream_id=row["stream_id"],
            version=row["version"],
            event_type=EventType(row["event_type"]),
            metadata=EventMetadata.from_dict(raw_metadata),
            payload=raw_payload,
            parent_id=UUID(str(row["parent_id"])) if row["parent_id"] else None,
            recorded_at=row["recorded_at"],
        )
