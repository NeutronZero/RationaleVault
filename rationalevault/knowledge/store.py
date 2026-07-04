"""RationaleVault Knowledge Store — Persistence layer for synthesized knowledge.

Mirrors the memory provider pattern with BaseKnowledgeProvider,
SQLiteKnowledgeProvider, and MarkdownKnowledgeProvider.
"""
from __future__ import annotations

import json
import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from rationalevault.knowledge.models import KnowledgeObject


class BaseKnowledgeProvider(ABC):
    """Abstract base class for Relay Knowledge Store providers."""

    @abstractmethod
    def add_knowledge(self, knowledge: KnowledgeObject) -> None:
        """Add or update a knowledge object."""
        pass

    @abstractmethod
    def get_all_knowledge(
        self,
        project_id: Optional[str] = None,
        transferable_only: bool = False,
    ) -> list[KnowledgeObject]:
        """Return knowledge objects, optionally filtered by project and transferability."""
        pass

    @abstractmethod
    def get_knowledge_by_id(self, knowledge_id: str) -> Optional[KnowledgeObject]:
        """Retrieve a specific knowledge object by ID."""
        pass

    @abstractmethod
    def search_knowledge(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None,
        transferable_only: bool = False,
    ) -> list[KnowledgeObject]:
        """Search knowledge objects by query string, optionally filtered."""
        pass

    @abstractmethod
    def update_lifecycle(self, knowledge_id: str, status: str) -> None:
        """Update the lifecycle status of a knowledge object."""
        pass


SELECT_COLUMNS = """
    SELECT id, version, title, content, knowledge_type, knowledge_domain,
           importance, lifecycle_status, tags, confidence, provenance,
           supporting_memory_ids, contradicting_memory_ids, superseded_by,
           created_at, updated_at, project_id, transferability
    FROM RationaleVault_knowledge
"""


class SQLiteKnowledgeProvider(BaseKnowledgeProvider):
    """SQLite-backed knowledge store."""

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
            CREATE TABLE IF NOT EXISTS rationalevault_knowledge (
                id TEXT PRIMARY KEY,
                version INTEGER,
                title TEXT,
                content TEXT,
                knowledge_type TEXT,
                knowledge_domain TEXT,
                importance TEXT,
                lifecycle_status TEXT,
                tags TEXT,
                confidence TEXT,
                provenance TEXT,
                supporting_memory_ids TEXT,
                contradicting_memory_ids TEXT,
                superseded_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                project_id TEXT DEFAULT '',
                transferability TEXT DEFAULT 'LOCAL_ONLY'
            )
            """
        )
        conn.commit()
        # Migration guards
        try:
            conn.execute("ALTER TABLE rationalevault_knowledge ADD COLUMN project_id TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE rationalevault_knowledge ADD COLUMN transferability TEXT DEFAULT 'LOCAL_ONLY'")
            conn.commit()
        except Exception:
            pass
        return conn

    def add_knowledge(self, knowledge: KnowledgeObject) -> None:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT version, content FROM rationalevault_knowledge WHERE id = ?",
                (knowledge.id,),
            )
            row = cursor.fetchone()
            if row:
                existing_ver, existing_content = row
                if existing_content != knowledge.content:
                    knowledge.version = existing_ver + 1

            conn.execute(
                """
                INSERT OR REPLACE INTO rationalevault_knowledge (
                    id, version, title, content, knowledge_type, knowledge_domain,
                    importance, lifecycle_status, tags, confidence, provenance,
                    supporting_memory_ids, contradicting_memory_ids, superseded_by,
                    created_at, updated_at, project_id, transferability
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    knowledge.id,
                    knowledge.version,
                    knowledge.title,
                    knowledge.content,
                    knowledge.knowledge_type.value,
                    knowledge.knowledge_domain.value,
                    knowledge.importance,
                    knowledge.lifecycle_status,
                    json.dumps(knowledge.tags),
                    json.dumps(knowledge.confidence.to_dict()),
                    json.dumps(knowledge.provenance.to_dict()),
                    json.dumps(knowledge.supporting_memory_ids),
                    json.dumps(knowledge.contradicting_memory_ids),
                    knowledge.superseded_by,
                    knowledge.created_at,
                    knowledge.updated_at,
                    knowledge.project_id,
                    knowledge.transferability,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_all_knowledge(
        self,
        project_id: Optional[str] = None,
        transferable_only: bool = False,
    ) -> list[KnowledgeObject]:
        records = []
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            params: list = []
            if project_id:
                params.append(project_id)

            if project_id and transferable_only:
                sql = SELECT_COLUMNS + " WHERE project_id = ? AND transferability IN ('REUSABLE', 'ORGANIZATIONAL')"
            elif project_id:
                sql = SELECT_COLUMNS + " WHERE project_id = ?"
            elif transferable_only:
                sql = SELECT_COLUMNS + " WHERE transferability IN ('REUSABLE', 'ORGANIZATIONAL')"
            else:
                sql = SELECT_COLUMNS

            cursor.execute(sql, params)
            for row in cursor.fetchall():
                records.append(self._row_to_knowledge(row))
        finally:
            conn.close()
        return records

    def get_knowledge_by_id(self, knowledge_id: str) -> Optional[KnowledgeObject]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, version, title, content, knowledge_type, knowledge_domain,
                       importance, lifecycle_status, tags, confidence, provenance,
                       supporting_memory_ids, contradicting_memory_ids, superseded_by,
                       created_at, updated_at, project_id, transferability
                FROM rationalevault_knowledge WHERE id = ?
                """,
                (knowledge_id,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_knowledge(row)
        finally:
            conn.close()
        return None

    def search_knowledge(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None,
        transferable_only: bool = False,
    ) -> list[KnowledgeObject]:
        records = []
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            q = f"%{query}%"
            params: list = [q, q, q]

            if project_id and transferable_only:
                params.append(project_id)
                params.append(limit)
                sql = (
                    SELECT_COLUMNS
                    + """
                    WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?)
                      AND project_id = ?
                      AND transferability IN ('REUSABLE', 'ORGANIZATIONAL')
                    ORDER BY created_at DESC LIMIT ?
                    """
                )
            elif project_id:
                params.append(project_id)
                params.append(limit)
                sql = (
                    SELECT_COLUMNS
                    + """
                    WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?)
                      AND project_id = ?
                    ORDER BY created_at DESC LIMIT ?
                    """
                )
            elif transferable_only:
                params.append(limit)
                sql = (
                    SELECT_COLUMNS
                    + """
                    WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?)
                      AND transferability IN ('REUSABLE', 'ORGANIZATIONAL')
                    ORDER BY created_at DESC LIMIT ?
                    """
                )
            else:
                params.append(limit)
                sql = (
                    SELECT_COLUMNS
                    + """
                    WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?)
                    ORDER BY created_at DESC LIMIT ?
                    """
                )

            cursor.execute(sql, params)
            for row in cursor.fetchall():
                records.append(self._row_to_knowledge(row))
        finally:
            conn.close()
        return records

    def update_lifecycle(self, knowledge_id: str, status: str) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE rationalevault_knowledge SET lifecycle_status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, knowledge_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _row_to_knowledge(self, row: tuple) -> KnowledgeObject:
        d = {
            "id": row[0],
            "version": row[1],
            "title": row[2],
            "content": row[3],
            "knowledge_type": row[4],
            "knowledge_domain": row[5],
            "importance": row[6],
            "lifecycle_status": row[7],
            "tags": json.loads(row[8]) if row[8] else [],
            "confidence": json.loads(row[9]) if row[9] else {},
            "provenance": json.loads(row[10]) if row[10] else {},
            "supporting_memory_ids": json.loads(row[11]) if row[11] else [],
            "contradicting_memory_ids": json.loads(row[12]) if row[12] else [],
            "superseded_by": row[13],
            "created_at": row[14],
            "updated_at": row[15],
            "project_id": row[16] if len(row) > 16 and row[16] else "",
            "transferability": row[17] if len(row) > 17 and row[17] else "LOCAL_ONLY",
        }
        return KnowledgeObject.from_dict(d)


class MarkdownKnowledgeProvider(BaseKnowledgeProvider):
    """Markdown-backed knowledge store."""

    def __init__(self, file_path: str | Path = None) -> None:
        if file_path is None:
            self.file_path = Path.cwd() / ".rationalevault" / "knowledge.md"
        else:
            self.file_path = Path(file_path)

    def _ensure_file(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("# RationaleVault Knowledge Corpus\n\n")

    def add_knowledge(self, knowledge: KnowledgeObject) -> None:
        records = self.get_all_knowledge()
        updated = False
        for idx, r in enumerate(records):
            if r.id == knowledge.id:
                if r.content != knowledge.content:
                    knowledge.version = r.version + 1
                records[idx] = knowledge
                updated = True
                break

        if not updated:
            records.append(knowledge)

        self._write_records(records)

    def get_all_knowledge(
        self,
        project_id: Optional[str] = None,
        transferable_only: bool = False,
    ) -> list[KnowledgeObject]:
        self._ensure_file()
        records = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()

            matches = re.finditer(
                r"<!--\s*knowledge_object\s*(\{.*?\})\s*-->", content, re.DOTALL
            )
            for m in matches:
                try:
                    data = json.loads(m.group(1))
                    records.append(KnowledgeObject.from_dict(data))
                except Exception:
                    pass
        except Exception:
            pass

        if project_id:
            records = [r for r in records if r.project_id == project_id]
        if transferable_only:
            records = [
                r for r in records
                if r.transferability in ("REUSABLE", "ORGANIZATIONAL")
            ]
        return records

    def get_knowledge_by_id(self, knowledge_id: str) -> Optional[KnowledgeObject]:
        records = self.get_all_knowledge()
        for r in records:
            if r.id == knowledge_id:
                return r
        return None

    def search_knowledge(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None,
        transferable_only: bool = False,
    ) -> list[KnowledgeObject]:
        records = self.get_all_knowledge(
            project_id=project_id, transferable_only=transferable_only
        )
        if not query:
            return records[:limit]

        query_clean = query.lower().strip()
        matched = []
        for r in records:
            if (
                query_clean in r.title.lower()
                or query_clean in r.content.lower()
                or any(query_clean in tag.lower() for tag in r.tags)
            ):
                matched.append(r)

        matched.sort(key=lambda x: x.importance, reverse=True)
        return matched[:limit]

    def update_lifecycle(self, knowledge_id: str, status: str) -> None:
        records = self.get_all_knowledge()
        for r in records:
            if r.id == knowledge_id:
                r.lifecycle_status = status
                r.updated_at = datetime.now().isoformat()
                break
        self._write_records(records)

    def _write_records(self, records: list[KnowledgeObject]) -> None:
        self._ensure_file()
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("# RationaleVault Knowledge Corpus\n\n")
            for r in records:
                f.write(f"<!-- knowledge_object {json.dumps(r.to_dict())} -->\n")
                f.write(f"## [{r.knowledge_type.value}] {r.title} (v{r.version})\n\n")
                f.write(f"{r.content.strip()}\n\n")
                f.write(f"* **Domain**: {r.knowledge_domain.value}\n")
                f.write(f"* **Importance**: {r.importance}\n")
                f.write(f"* **Confidence**: {r.confidence.score:.2f}\n")
                f.write(f"* **Status**: {r.lifecycle_status}\n")
                f.write(f"* **Tags**: {', '.join(r.tags)}\n")
                f.write(f"* **Source Memories**: {', '.join(r.supporting_memory_ids)}\n")
                f.write(f"* **Source Events**: {', '.join(r.provenance.source_event_ids)}\n")
                f.write("\n---\n\n")
