import pytest

from rationalevault.ledger.interface import Ledger


def test_ledger_is_abstract():
    with pytest.raises(TypeError):
        Ledger()


def test_ledger_has_append():
    assert hasattr(Ledger, "append")


def test_ledger_has_read_stream():
    assert hasattr(Ledger, "read_stream")


def test_ledger_has_read_from():
    assert hasattr(Ledger, "read_from")


def test_ledger_has_exists():
    assert hasattr(Ledger, "exists")


def test_ledger_has_stream_exists():
    assert hasattr(Ledger, "stream_exists")