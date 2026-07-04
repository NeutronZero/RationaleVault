from __future__ import annotations

from rationalevault.memory.models import MemoryRecord, MemoryType
from rationalevault.knowledge.contradiction import ContradictionEngine, ContradictionFinding


def _create_record(doc_id: str, title: str, content: str) -> MemoryRecord:
    return MemoryRecord(
        id=doc_id, version=1, title=title, content=content,
        memory_type=MemoryType.DECISION, importance="medium", lifecycle_status="active",
        source_event_ids=["1"], source_type="test", project_id="test"
    )


def test_detect_duplicate_conflicting_ids() -> None:
    r1 = _create_record("dup-1", "Original Title", "Original Content")
    r2 = _create_record("dup-1", "Conflicting Title", "Different Content")

    findings = ContradictionEngine.detect([r1, r2])
    assert len(findings) == 1
    assert findings[0].contradiction_type == "duplicate_conflicting"
    assert findings[0].severity == "critical"


def test_detect_exclusive_config() -> None:
    # Exclusive configuration keys
    r1 = _create_record("rule-1", "DB configuration", "database = postgres\npool_size: 10")
    r2 = _create_record("rule-2", "Alternative DB", "database = sqlite\npool_size: 20")

    findings = ContradictionEngine.detect([r1, r2])
    assert len(findings) >= 2 # database and pool_size are mutually exclusive
    types = [f.contradiction_type for f in findings]
    assert "exclusive_config" in types


def test_detect_opposite_assertions() -> None:
    r1 = _create_record("rule-1", "Pooling Rule", "always use postgres connection pooling")
    r2 = _create_record("rule-2", "Opposing Pooling", "avoid postgres connection pooling")

    findings = ContradictionEngine.detect([r1, r2])
    assert len(findings) >= 1
    assert findings[0].contradiction_type == "opposite_assertion"
    assert findings[0].severity == "warning"


def test_multiple_contradictions_preservation() -> None:
    r1 = _create_record("rule-1", "DB postgres", "database = postgres")
    r2 = _create_record("rule-2", "DB sqlite", "database = sqlite")
    r3 = _create_record("rule-3", "DB mysql", "database = mysql")

    findings = ContradictionEngine.detect([r1, r2, r3])
    # r1 vs r2, r1 vs r3, r2 vs r3
    assert len(findings) == 3
    for f in findings:
        assert f.contradiction_type == "exclusive_config"
