"""
RationaleVault Database Connection — psycopg3 synchronous connection management.

Design choices:
  - Synchronous psycopg3 throughout V1. Async adds complexity without
    performance benefit at V1's local, low-volume workload.
  - Each operation opens and closes its own connection unless the caller
    passes an existing connection for multi-step transactions.
  - Connection parameters are read from environment variables (via .env).

Environment variables:
    RELAY_DB_HOST     (default: localhost)
    RELAY_DB_PORT     (default: 5432)
    RELAY_DB_NAME     (default: relay)
    RELAY_DB_USER     (default: relay)
    RELAY_DB_PASSWORD (default: relay)
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row


def get_dsn() -> str:
    """
    Build a libpq connection string from environment variables.
    Falls back to sensible defaults that match docker-compose.yml.
    """
    host = os.environ.get("RELAY_DB_HOST", "localhost")
    port = os.environ.get("RELAY_DB_PORT", "5432")
    dbname = os.environ.get("RELAY_DB_NAME", "relay")
    user = os.environ.get("RELAY_DB_USER", "relay")
    password = os.environ.get("RELAY_DB_PASSWORD", "relay")
    return f"host={host} port={port} dbname={dbname} user={user} password={password} connect_timeout=3"


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    """
    Context manager that yields a psycopg3 connection with dict_row factory.

    Behaviour:
      - Commits automatically on clean exit.
      - Rolls back on any exception before re-raising.
      - Always closes the connection in the finally block.

    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    conn = psycopg.connect(get_dsn(), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
