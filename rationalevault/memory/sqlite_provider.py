from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from rationalevault.memory.base import BaseMemoryProvider
from rationalevault.memory.models import MemoryRecord


class SQLiteMemoryProvider(BaseMemoryProvider):
    def __init__(self, db_path: str | Path = None) -> None:
        if db_path is None:
            self.db_path = Path.cwd() / ".rationalevault" / "rationalevault.db"
        else:
            self.db_path = Path(db_path)

    def _get_conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rationalevault_memories (
                id TEXT PRIMARY KEY,
                version INTEGER,
                title TEXT,
                content TEXT,
                memory_type TEXT,
                importance TEXT,
                lifecycle_status TEXT,
                source_event_ids TEXT,
                source_type TEXT,
                tags TEXT,
                confidence REAL,
                retrieval_priority REAL,
                reference_count INTEGER DEFAULT 0,
                last_referenced_at TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()
        # Migration guard
        try:
            conn.execute("ALTER TABLE rationalevault_memories ADD COLUMN reference_count INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE rationalevault_memories ADD COLUMN last_referenced_at TEXT")
            conn.commit()
        except Exception:
            pass
        return conn

    def get_all_records(self) -> list[MemoryRecord]:
        records = []
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, version, title, content, memory_type, importance, lifecycle_status,
                       source_event_ids, source_type, tags, confidence, retrieval_priority,
                       reference_count, last_referenced_at, created_at
                FROM rationalevault_memories
                """
            )
            for row in cursor.fetchall():
                from rationalevault.memory.models import MemoryType
                records.append(
                    MemoryRecord(
                        id=row[0],
                        version=row[1],
                        title=row[2],
                        content=row[3],
                        memory_type=MemoryType(row[4]),
                        importance=row[5],
                        lifecycle_status=row[6],
                        source_event_ids=json.loads(row[7]),
                        source_type=row[8],
                        tags=json.loads(row[9]),
                        confidence=row[10],
                        retrieval_priority=row[11],
                        reference_count=row[12] if row[12] is not None else 0,
                        last_referenced_at=row[13],
                        created_at=row[14],
                    )
                )
        finally:
            conn.close()
        return records

    def add_record(self, record: MemoryRecord) -> None:
        conn = self._get_conn()
        try:
            # Check version increment
            cursor = conn.cursor()
            cursor.execute("SELECT version, content FROM rationalevault_memories WHERE id = ?", (record.id,))
            row = cursor.fetchone()
            if row:
                existing_ver, existing_content = row
                if existing_content != record.content:
                    record.version = existing_ver + 1

            conn.execute(
                """
                INSERT OR REPLACE INTO rationalevault_memories (
                    id, version, title, content, memory_type, importance, lifecycle_status,
                    source_event_ids, source_type, tags, confidence, retrieval_priority,
                    reference_count, last_referenced_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.version,
                    record.title,
                    record.content,
                    record.memory_type.value,
                    record.importance,
                    record.lifecycle_status,
                    json.dumps(record.source_event_ids),
                    record.source_type,
                    json.dumps(record.tags),
                    record.confidence,
                    record.retrieval_priority,
                    record.reference_count,
                    record.last_referenced_at,
                    record.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def search_records(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        records = []
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            q = f"%{query}%"
            cursor.execute(
                """
                SELECT id, version, title, content, memory_type, importance, lifecycle_status,
                       source_event_ids, source_type, tags, confidence, retrieval_priority,
                       reference_count, last_referenced_at, created_at
                FROM rationalevault_memories 
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? 
                ORDER BY retrieval_priority DESC LIMIT ?
                """,
                (q, q, q, limit),
            )
            for row in cursor.fetchall():
                from rationalevault.memory.models import MemoryType
                records.append(
                    MemoryRecord(
                        id=row[0],
                        version=row[1],
                        title=row[2],
                        content=row[3],
                        memory_type=MemoryType(row[4]),
                        importance=row[5],
                        lifecycle_status=row[6],
                        source_event_ids=json.loads(row[7]),
                        source_type=row[8],
                        tags=json.loads(row[9]),
                        confidence=row[10],
                        retrieval_priority=row[11],
                        reference_count=row[12] if row[12] is not None else 0,
                        last_referenced_at=row[13],
                        created_at=row[14],
                    )
                )
        finally:
            conn.close()
        return records
