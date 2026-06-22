from __future__ import annotations

import os
from pathlib import Path
from rationalevault.db.base import BaseEventStore
from rationalevault.db.sqlite_store import SQLiteEventStore
from rationalevault.db.postgres_store import PostgresEventStore

try:
    import yaml
except ImportError:
    yaml = None


def get_event_store() -> BaseEventStore:
    """
    Resolves and returns the configured EventStore backend.
    Checks the local project configuration in .relay/project.yaml first.
    Falls back to SQLiteEventStore using .relay/relay.db if config is missing or SQLite is configured.
    """
    project_root = Path.cwd()
    project_yaml_path = project_root / ".rationalevault" / "project.yaml"

    if project_yaml_path.exists() and yaml:
        try:
            with open(project_yaml_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            storage_config = config.get("storage", {})
            backend = storage_config.get("backend", "sqlite").lower()

            if backend == "postgres":
                return PostgresEventStore()
            elif backend == "sqlite":
                db_path = storage_config.get("database", ".relay/relay.db")
                return SQLiteEventStore(db_path=db_path)
        except Exception:
            pass

    # Simple fallback: Check environment variable or use default SQLite
    if os.environ.get("RELAY_USE_POSTGRES") == "1":
        return PostgresEventStore()

    return SQLiteEventStore()
