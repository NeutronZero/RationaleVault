from __future__ import annotations

import json
import uuid
from typing import Any, Iterator, Optional
from uuid import UUID

import psycopg

from rationalevault.db.base import BaseEventStore
from rationalevault.db.connection import get_connection
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


class PostgresEventStore(BaseEventStore):
    """
    Append-only event ledger backed by PostgreSQL.
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
        def _run(c: psycopg.Connection) -> EventRecord:
            with c.cursor() as cur:
                # Advisory lock keyed by project_id UUID int representation
                lock_key = UUID(str(project_id)).int & 0x7FFFFFFFFFFFFFFF
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))

                # Compute next per-project version
                cur.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 AS next_version "
                    "FROM rationalevault_events WHERE project_id = %s",
                    (str(project_id),),
                )
                next_version: int = cur.fetchone()["next_version"]

                event_id = uuid.uuid4()

                cur.execute(
                    """
                    INSERT INTO rationalevault_events (
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
                schema_version=payload.get("schema_version", 1) if isinstance(payload, dict) else 1,
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
        sql = """
            SELECT event_sequence, id, project_id, stream_id, version,
                   event_type, metadata, payload, parent_id, recorded_at
            FROM rationalevault_events
            WHERE project_id = %s
              AND event_sequence > %s
            ORDER BY event_sequence ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(project_id), since_sequence))
                return [self._row_to_record(row) for row in cur]

    def replay_stream(
        self,
        project_id: UUID,
        since_sequence: int = 0,
    ) -> Iterator[EventRecord]:
        sql = """
            SELECT event_sequence, id, project_id, stream_id, version,
                   event_type, metadata, payload, parent_id, recorded_at
            FROM rationalevault_events
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
        sql = """
            SELECT event_sequence, id, project_id, stream_id, version,
                   event_type, metadata, payload, parent_id, recorded_at
            FROM rationalevault_events
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
        sql = "SELECT COUNT(*) AS cnt FROM rationalevault_events WHERE project_id = %s"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(project_id),))
                return cur.fetchone()["cnt"]

    def get_session_events(self, project_id: UUID, session_id: str) -> list[EventRecord]:
        sql = """
            SELECT event_sequence, id, project_id, stream_id, version,
                   event_type, metadata, payload, parent_id, recorded_at
            FROM rationalevault_events
            WHERE project_id = %s
              AND metadata->>'session_id' = %s
            ORDER BY event_sequence ASC
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(project_id), session_id))
                return [self._row_to_record(row) for row in cur.fetchall()]

    def get_last_session_id(self, project_id: UUID) -> Optional[str]:
        sql = """
            SELECT metadata->>'session_id' AS session_id
            FROM rationalevault_events
            WHERE project_id = %s
            ORDER BY event_sequence DESC
            LIMIT 1
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(project_id),))
                row = cur.fetchone()
                return row["session_id"] if row else None

    def get_recent_events(self, project_id: UUID, limit: int = 20) -> list[EventRecord]:
        sql = """
            SELECT event_sequence, id, project_id, stream_id, version,
                   event_type, metadata, payload, parent_id, recorded_at
            FROM rationalevault_events
            WHERE project_id = %s
            ORDER BY event_sequence DESC
            LIMIT %s
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(project_id), limit))
                return [self._row_to_record(row) for row in cur.fetchall()]


    # ── Internal ───────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_record(row: dict) -> EventRecord:
        raw_metadata = row["metadata"]
        if isinstance(raw_metadata, str):
            raw_metadata = json.loads(raw_metadata)

        raw_payload = row["payload"]
        if isinstance(raw_payload, str):
            raw_payload = json.loads(raw_payload)

        schema_version = 1
        if "schema_version" in row:
            schema_version = row["schema_version"]
        elif isinstance(raw_payload, dict) and "schema_version" in raw_payload:
            schema_version = raw_payload["schema_version"]

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
            schema_version=schema_version,
        )
