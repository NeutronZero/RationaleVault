"""
Relay test suite — conftest.py

Database tests are skipped unless RELAY_DB_TEST_ENABLED=1 is set.
This allows pure-Python tests (reducers, compilers) to run without
a live PostgreSQL connection.

To run all tests including database tests:
    set RELAY_DB_TEST_ENABLED=1
    pytest tests/unit/ -v
"""
from __future__ import annotations

import os
import uuid
from uuid import UUID

import pytest


DB_REQUIRED = pytest.mark.skipif(
    os.environ.get("RELAY_DB_TEST_ENABLED") != "1",
    reason=(
        "Set RELAY_DB_TEST_ENABLED=1 and ensure the database is initialized "
        "to run database integration tests."
    ),
)


@pytest.fixture
def fresh_project_id() -> UUID:
    """Return a fresh project UUID for test isolation."""
    return uuid.uuid4()
