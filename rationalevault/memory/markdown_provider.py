from __future__ import annotations

import json
import re
import threading
import sys
from pathlib import Path
from filelock import FileLock, Timeout
from rationalevault.memory.base import BaseMemoryProvider
from rationalevault.memory.models import MemoryRecord


_provider_locks = {}
_provider_locks_lock = threading.Lock()


class MarkdownMemoryProvider(BaseMemoryProvider):
    def __init__(self, file_path: str | Path = None) -> None:
        if file_path is None:
            self.file_path = Path.cwd() / ".rationalevault" / "memory.md"
        else:
            self.file_path = Path(file_path).resolve()
        
        # Layered locks: thread-safe (across instances) and multi-process safe
        with _provider_locks_lock:
            key = str(self.file_path)
            if key not in _provider_locks:
                _provider_locks[key] = threading.RLock()
            self._thread_lock = _provider_locks[key]
            
        self._file_lock = FileLock(str(self.file_path) + ".lock", timeout=10)

    def _ensure_file(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("# RationaleVault Cognitive Memory Corpus\n\n")

    def get_all_records(self) -> list[MemoryRecord]:
        self._ensure_file()
        records = []
        try:
            with self._thread_lock:
                with self._file_lock:
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        content = f.read()

            # Find all JSON metadata blocks embedded in HTML comments
            matches = re.finditer(r"<!--\s*memory_record\s*(\{.*?\})\s*-->", content, re.DOTALL)
            for m in matches:
                try:
                    data = json.loads(m.group(1))
                    records.append(MemoryRecord.from_dict(data))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                    sys.stderr.write(f"Warning: Failed to parse memory record JSON block: {e}\n")
        except FileNotFoundError:
            pass
        except Timeout:
            sys.stderr.write(f"Warning: Failed to acquire lock for {self.file_path}\n")
        except Exception as e:
            sys.stderr.write(f"Warning: Unexpected error reading memory records: {e}\n")
        return records

    def add_record(self, record: MemoryRecord) -> None:
        with self._thread_lock:
            with self._file_lock:
                records = self.get_all_records()
            # Find if duplicate ID exists, if so we update it (supersede/overwrite)
            updated = False
            for idx, r in enumerate(records):
                if r.id == record.id:
                    # Increment version if content is different
                    if r.content != record.content:
                        record.version = r.version + 1
                    records[idx] = record
                    updated = True
                    break

            if not updated:
                records.append(record)

            self._write_records(records)

    def _write_records(self, records: list[MemoryRecord]) -> None:
        self._ensure_file()
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("# RationaleVault Cognitive Memory Corpus\n\n")
            for r in records:
                f.write(f"<!-- memory_record {json.dumps(r.to_dict())} -->\n")
                f.write(f"## [{r.memory_type.value}] {r.title} (v{r.version})\n\n")
                f.write(f"{r.content.strip()}\n\n")
                f.write(f"* **Importance**: {r.importance}\n")
                f.write(f"* **Confidence**: {r.confidence:.2f}\n")
                f.write(f"* **Reference Count**: {r.reference_count}\n")
                f.write(f"* **Last Referenced**: {r.last_referenced_at or 'Never'}\n")
                f.write(f"* **Tags**: {', '.join(r.tags)}\n")
                f.write(f"* **Source Type**: {r.source_type}\n")
                f.write(f"* **Source Events**: {', '.join(r.source_event_ids)}\n")
                f.write("\n---\n\n")

    def search_records(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        records = self.get_all_records()
        if not query:
            return records[:limit]

        query_clean = query.lower().strip()
        matched = []
        for r in records:
            # Check title, content, or tags
            if (
                query_clean in r.title.lower() or
                query_clean in r.content.lower() or
                any(query_clean in tag.lower() for tag in r.tags)
            ):
                matched.append(r)

        # Sort by retrieval priority descending
        matched.sort(key=lambda x: x.retrieval_priority, reverse=True)
        return matched[:limit]
