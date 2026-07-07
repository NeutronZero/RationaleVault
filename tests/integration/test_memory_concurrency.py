import pytest
import uuid
import threading
import concurrent.futures
from rationalevault.memory.markdown_provider import MarkdownMemoryProvider
from rationalevault.memory.models import MemoryRecord, MemoryType

def test_markdown_provider_concurrency_stress(tmp_path):
    """
    Stress test for MarkdownMemoryProvider concurrency.
    Runs multiple workers, each writing multiple records concurrently.
    Verifies no corruption, no missing records, and stable state.
    """
    db_file = tmp_path / "memory.md"
    
    workers = 8
    writes_per_worker = 20
    
    def worker_task(worker_id):
        provider = MarkdownMemoryProvider(db_file)
        for i in range(writes_per_worker):
            record = MemoryRecord(
                id=str(uuid.uuid4()),
                version=1,
                memory_type=MemoryType.RESEARCH,
                title=f"Worker {worker_id} Record {i}",
                content=f"Content for worker {worker_id} iter {i}",
                importance="low",
                confidence=0.9,
                lifecycle_status="active",
                source_event_ids=[],
                source_type="test"
            )
            provider.add_record(record)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker_task, w) for w in range(workers)]
        for f in concurrent.futures.as_completed(futures):
            f.result() # Will raise if any thread failed
            
    # Verification
    final_provider = MarkdownMemoryProvider(db_file)
    records = final_provider.get_all_records()
    
    expected_count = workers * writes_per_worker
    assert len(records) == expected_count, f"Expected {expected_count} records, got {len(records)}"
    
    # Check no corruption by validating all records
    for r in records:
        assert r.title.startswith("Worker ")
        assert "Content" in r.content
