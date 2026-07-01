"""Unit tests for database connection configuration."""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch

from rationalevault.db.connection import get_dsn


def test_get_dsn_default() -> None:
    with patch.dict(os.environ, {}, clear=True):
        dsn = get_dsn()
        assert "password=" not in dsn
        assert "host=localhost" in dsn
        assert "port=5432" in dsn
        assert "dbname=relay" in dsn
        assert "user=relay" in dsn


def test_get_dsn_with_password() -> None:
    with patch.dict(os.environ, {"RELAY_DB_PASSWORD": "secret_pass"}):
        dsn = get_dsn()
        assert "password=secret_pass" in dsn


def test_get_dsn_production_with_password() -> None:
    with patch.dict(os.environ, {"RELAY_ENV": "production", "RELAY_DB_PASSWORD": "prod_pass"}):
        dsn = get_dsn()
        assert "password=prod_pass" in dsn


def test_get_dsn_production_missing_password_raises() -> None:
    with patch.dict(os.environ, {"RELAY_ENV": "production"}, clear=True):
        with pytest.raises(RuntimeError) as exc_info:
            get_dsn()
        assert "RELAY_DB_PASSWORD must be set in production" in str(exc_info.value)
