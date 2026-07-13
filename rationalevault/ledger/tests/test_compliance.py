import pytest

from rationalevault.ledger.compliance.vectors import load_vectors
from rationalevault.ledger.compliance.validator import LedgerComplianceValidator
from rationalevault.ledger.storage.memory import MemoryLedger
from rationalevault.ledger.storage.sqlite import SQLiteLedger


VECTORS = load_vectors()


def _memory_factory():
    return MemoryLedger()


@pytest.fixture
def sqlite_factory(tmp_path):
    db_path = tmp_path / "compliance.db"

    def _factory():
        return SQLiteLedger(str(db_path))

    return _factory


@pytest.mark.parametrize("vector_name", sorted(VECTORS.keys()))
def test_compliance_memory(vector_name):
    vector = VECTORS[vector_name]
    validator = LedgerComplianceValidator(_memory_factory)
    results = validator.validate_vector(vector)
    failures = [r for r in results if not r.passed]
    assert not failures, (
        f"Memory backend failed {vector_name}: "
        + "; ".join(f"{r.message} (expected={r.expected}, actual={r.actual})" for r in failures)
    )


@pytest.mark.parametrize("vector_name", sorted(VECTORS.keys()))
def test_compliance_sqlite(vector_name, sqlite_factory):
    vector = VECTORS[vector_name]
    validator = LedgerComplianceValidator(sqlite_factory)
    results = validator.validate_vector(vector)
    failures = [r for r in results if not r.passed]
    assert not failures, (
        f"SQLite backend failed {vector_name}: "
        + "; ".join(f"{r.message} (expected={r.expected}, actual={r.actual})" for r in failures)
    )
