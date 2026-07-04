"""Tests for database connection configuration."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from rationalevault.db.connection import get_dsn


class TestGetDsn:
    def test_default_dsn(self) -> None:
        env = {k: v for k, v in os.environ.items() if not k.startswith("RELAY_DB_")}
        with patch.dict(os.environ, env, clear=True):
            dsn = get_dsn()
            assert "host=localhost" in dsn
            assert "port=5432" in dsn
            assert "dbname=relay" in dsn
            assert "user=relay" in dsn
            assert "password" not in dsn

    def test_password_included_when_set(self) -> None:
        env = {
            "RELAY_DB_HOST": "db.example.com",
            "RELAY_DB_PORT": "5433",
            "RELAY_DB_NAME": "mydb",
            "RELAY_DB_USER": "admin",
            "RELAY_DB_PASSWORD": "s3cret",
        }
        with patch.dict(os.environ, env, clear=True):
            dsn = get_dsn()
            assert "host=db.example.com" in dsn
            assert "password=s3cret" in dsn

    def test_special_chars_in_password_preserved(self) -> None:
        env = {
            "RELAY_DB_HOST": "localhost",
            "RELAY_DB_PORT": "5432",
            "RELAY_DB_NAME": "relay",
            "RELAY_DB_USER": "relay",
            "RELAY_DB_PASSWORD": "pass word with spaces",
        }
        with patch.dict(os.environ, env, clear=True):
            dsn = get_dsn()
            assert "password=pass word with spaces" in dsn

    def test_production_requires_password(self) -> None:
        """Production mode without password should raise RuntimeError."""
        env = {
            "RELAY_ENV": "production",
            "RELAY_DB_HOST": "localhost",
            "RELAY_DB_PORT": "5432",
            "RELAY_DB_NAME": "relay",
            "RELAY_DB_USER": "relay",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="RELAY_DB_PASSWORD must be set"):
                get_dsn()
