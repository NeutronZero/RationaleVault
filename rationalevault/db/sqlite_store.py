from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator, Optional
from uuid import UUID

from rationalevault.db.base import BaseEventStore
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


class SQLiteEventStore(BaseEventStore):
    """
    Append-only event ledger backed by SQLite.
    """

    def __init__(self, db_path: str = ".relay/relay.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        # Use isolation_level=None for manual transaction control
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        from pathlib import Path
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rationalevault_events (
                    event_sequence  INTEGER PRIMARY KEY AUTOINCREMENT,
                    id              TEXT NOT NULL UNIQUE,
                    project_id      TEXT NOT NULL,
                    stream_id       TEXT NOT NULL,
                    version         INTEGER NOT NULL,
                    event_type      TEXT NOT NULL,
                    metadata        TEXT NOT NULL,
                    payload         TEXT NOT NULL,
                    parent_id       TEXT,
                    recorded_at     TEXT NOT NULL,
                    UNIQUE (project_id, version)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_relay_events_project ON rationalevault_events(project_id);")

            # Snapshot cache table (V2)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rationalevault_snapshots (
                    id                TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                    project_id        TEXT NOT NULL,
                    projection_name   TEXT NOT NULL,
                    sequence          INTEGER NOT NULL,
                    payload           TEXT NOT NULL,
                    schema_version    INTEGER NOT NULL DEFAULT 1,
                    projection_version INTEGER NOT NULL DEFAULT 1,
                    snapshot_hash     TEXT NOT NULL,
                    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_lookup
                    ON rationalevault_snapshots (project_id, projection_name, sequence DESC);
            """)

    # ── Write ──────────────────────────────────────────────────────────────

    def append_event(
        self,
        project_id: UUID,
        stream_id: str,
        event_type: EventType,
        payload: dict[str, Any],
        metadata: EventMetadata,
        parent_id: Optional[UUID] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> EventRecord:
        
        def _run(c: sqlite3.Connection) -> EventRecord:
            # BEGIN IMMEDIATE transaction enforces write lock on SQLite
            c.execute("BEGIN IMMEDIATE TRANSACTION;")
            try:
                # Compute next per-project version
                cur = c.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 AS next_version "
                    "FROM rationalevault_events WHERE project_id = ?",
                    (str(project_id),),
                )
                next_version = cur.fetchone()["next_version"]

                event_id = uuid.uuid4()
                recorded_at = datetime.now(timezone.utc).isoformat()

                c.execute(
                    """
                    INSERT INTO rationalevault_events (
                        id, project_id, stream_id, version,
                        event_type, metadata, payload, parent_id, recorded_at
                    ) VALUES (
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
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
                        recorded_at,
                    ),
                )
                
                # Fetch sequence ID
                cur = c.execute("SELECT last_insert_rowid() AS seq;")
                event_sequence = cur.fetchone()["seq"]
                c.execute("COMMIT;")
            except Exception:
                c.execute("ROLLBACK;")
                raise

            return EventRecord(
                event_sequence=event_sequence,
                id=event_id,
                project_id=project_id,
                stream_id=stream_id,
                version=next_version,
                event_type=event_type,
                metadata=metadata,
                payload=payload,
                parent_id=parent_id,
                recorded_at=datetime.fromisoformat(recorded_at),
                schema_version=payload.get("schema_version", 1) if isinstance(payload, dict) else 1,
            )

        if conn is not None:
            return _run(conn)
        
        c = self._get_conn()
        try:
            return _run(c)
        finally:
            c.close()

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
            WHERE project_id = ?
              AND event_sequence > ?
            ORDER BY event_sequence ASC
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id), since_sequence))
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
            WHERE project_id = ?
              AND event_sequence > ?
            ORDER BY event_sequence ASC
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id), since_sequence))
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
            WHERE project_id = ?
              AND stream_id = ?
              AND event_sequence > ?
            ORDER BY event_sequence ASC
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id), stream_id, since_sequence))
            return [self._row_to_record(row) for row in cur.fetchall()]

    def get_event_count(self, project_id: UUID) -> int:
        sql = "SELECT COUNT(*) AS cnt FROM rationalevault_events WHERE project_id = ?"
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id),))
            return cur.fetchone()["cnt"]

    def get_session_events(self, project_id: UUID, session_id: str) -> list[EventRecord]:
        sql = """
            SELECT event_sequence, id, project_id, stream_id, version,
                   event_type, metadata, payload, parent_id, recorded_at
            FROM rationalevault_events
            WHERE project_id = ?
              AND json_extract(metadata, '$.session_id') = ?
            ORDER BY event_sequence ASC
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id), session_id))
            return [self._row_to_record(row) for row in cur.fetchall()]

    def get_last_session_id(self, project_id: UUID) -> Optional[str]:
        sql = """
            SELECT json_extract(metadata, '$.session_id') AS session_id
            FROM rationalevault_events
            WHERE project_id = ?
            ORDER BY event_sequence DESC
            LIMIT 1
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id),))
            row = cur.fetchone()
            return row["session_id"] if row else None

    def get_recent_events(self, project_id: UUID, limit: int = 20) -> list[EventRecord]:
        sql = """
            SELECT event_sequence, id, project_id, stream_id, version,
                   event_type, metadata, payload, parent_id, recorded_at
            FROM rationalevault_events
            WHERE project_id = ?
            ORDER BY event_sequence DESC
            LIMIT ?
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id), limit))
            return [self._row_to_record(row) for row in cur.fetchall()]


    # ── Snapshots (V2) ──────────────────────────────────────────────────────

    def load_latest_raw(
        self,
        project_id: UUID,
        projection_name: str,
    ):
        """
        Return the raw payload row for the latest snapshot, or None.

        Storage does NOT validate. It returns raw data; the SnapshotManager
        handles deserialization and validation.
        """
        sql = """
            SELECT payload, schema_version, projection_version,
                   sequence, snapshot_hash
            FROM rationalevault_snapshots
            WHERE project_id = ? AND projection_name = ?
            ORDER BY sequence DESC
            LIMIT 1
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id), projection_name))
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "payload": json.loads(row["payload"]),
                "schema_version": row["schema_version"],
                "projection_version": row["projection_version"],
                "sequence": row["sequence"],
                "snapshot_hash": row["snapshot_hash"],
            }

    def save_snapshot(
        self,
        project_id: UUID,
        projection_name: str,
        payload,
    ) -> None:
        """
        Persist a snapshot to durable storage.

        Old snapshots are retained for audit (not deleted on save).
        """
        payload_dict = payload.to_dict(exclude_hash=True)
        sql = """
            INSERT INTO rationalevault_snapshots
                (id, project_id, projection_name, sequence, payload,
                 schema_version, projection_version, snapshot_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        snapshot_id = uuid.uuid4().hex
        with self._get_conn() as conn:
            conn.execute(
                sql,
                (
                    snapshot_id,
                    str(project_id),
                    projection_name,
                    payload.sequence,
                    json.dumps(payload_dict),
                    payload.schema_version,
                    payload.projection_version,
                    payload.snapshot_hash,
                ),
            )

    def delete_snapshots_before(
        self,
        project_id: UUID,
        projection_name: str,
        sequence: int,
    ) -> int:
        """
        Delete snapshots older than the given sequence number.

        Returns the number of snapshots deleted.
        """
        sql = """
            DELETE FROM rationalevault_snapshots
            WHERE project_id = ?
              AND projection_name = ?
              AND sequence < ?
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id), projection_name, sequence))
            return cur.rowcount

    def get_latest_snapshot_sequence(
        self,
        project_id: UUID,
        projection_name: str,
    ) -> Optional[int]:
        """Return the sequence number of the latest snapshot, or None."""
        sql = """
            SELECT sequence FROM rationalevault_snapshots
            WHERE project_id = ? AND projection_name = ?
            ORDER BY sequence DESC
            LIMIT 1
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id), projection_name))
            row = cur.fetchone()
            return row["sequence"] if row else None

    def get_latest_sequence(self, project_id: UUID) -> int:
        """Return the maximum event_sequence for the project, or 0."""
        sql = (
            "SELECT COALESCE(MAX(event_sequence), 0) AS seq "
            "FROM rationalevault_events WHERE project_id = ?"
        )
        with self._get_conn() as conn:
            cur = conn.execute(sql, (str(project_id),))
            return cur.fetchone()["seq"]

    # ── Internal ───────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> EventRecord:
        raw_metadata = json.loads(row["metadata"])
        raw_payload = json.loads(row["payload"])

        # Convert recorded_at text to datetime
        recorded_at_str = row["recorded_at"]
        try:
            # Strip Z and convert to datetime
            if recorded_at_str.endswith("Z"):
                recorded_at_str = recorded_at_str[:-1] + "+00:00"
            recorded_at = datetime.fromisoformat(recorded_at_str)
        except (ValueError, TypeError) as e:
            import sys
            sys.stderr.write(f"Warning: Failed to parse recorded_at datetime '{recorded_at_str}': {e}\n")
            recorded_at = datetime.now(timezone.utc)

        schema_version = 1
        if "schema_version" in row.keys():
            schema_version = row["schema_version"]
        elif isinstance(raw_payload, dict) and "schema_version" in raw_payload:
            schema_version = raw_payload["schema_version"]

        return EventRecord(
            event_sequence=row["event_sequence"],
            id=UUID(row["id"]),
            project_id=UUID(row["project_id"]),
            stream_id=row["stream_id"],
            version=row["version"],
            event_type=EventType(row["event_type"]),
            metadata=EventMetadata.from_dict(raw_metadata),
            payload=raw_payload,
            parent_id=UUID(row["parent_id"]) if row["parent_id"] else None,
            recorded_at=recorded_at,
            schema_version=schema_version,
        )
