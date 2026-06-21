"""
Relay Database Initializer — applies SQL migrations in order.

Idempotent: already-applied migrations are skipped.
Tracks applied migrations in the relay_migrations table.

Usage:
    python scripts/init_db.py
    python scripts/init_db.py --reset    # WARNING: destroys all data
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make relay package importable from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import psycopg
from relay.db.connection import get_dsn

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"

MIGRATION_FILES = [
    "0001_initial.sql",
    "0002_indexes.sql",
]


def create_migrations_table(conn: psycopg.Connection) -> None:
    """Create relay_migrations table if it does not exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS relay_migrations (
                filename    TEXT        PRIMARY KEY,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    conn.commit()


def get_applied_migrations(conn: psycopg.Connection) -> set[str]:
    """Return the set of already-applied migration filenames."""
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM relay_migrations")
        return {row[0] for row in cur.fetchall()}


def apply_migration(conn: psycopg.Connection, filename: str, sql: str) -> None:
    """Apply a single migration file and record it in relay_migrations."""
    print(f"  Applying {filename} ...", end=" ", flush=True)
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            "INSERT INTO relay_migrations (filename) VALUES (%s) "
            "ON CONFLICT (filename) DO NOTHING",
            (filename,),
        )
    conn.commit()
    print("OK")


def reset_database(conn: psycopg.Connection) -> None:
    """Drop all Relay tables. Destroys all data."""
    print("  [WARNING] Resetting database -- dropping all Relay tables...")
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS relay_events CASCADE")
        cur.execute("DROP TABLE IF EXISTS relay_migrations CASCADE")
    conn.commit()
    print("  Tables dropped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize the Relay PostgreSQL database."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all Relay tables. WARNING: destroys all data.",
    )
    args = parser.parse_args()

    dsn = get_dsn()
    print(f"\nRelay Database Initializer")
    print("=" * 50)
    print(f"Connecting: {dsn}")

    conn = psycopg.connect(dsn)
    try:
        if args.reset:
            reset_database(conn)

        print("\nApplying migrations:")
        create_migrations_table(conn)
        applied = get_applied_migrations(conn)

        skipped = 0
        applied_count = 0
        for filename in MIGRATION_FILES:
            if filename in applied:
                print(f"  Skipping {filename} (already applied)")
                skipped += 1
                continue
            migration_path = MIGRATIONS_DIR / filename
            if not migration_path.exists():
                print(f"  ERROR: Migration file not found: {migration_path}")
                sys.exit(1)
            apply_migration(conn, filename, migration_path.read_text())
            applied_count += 1

        print(f"\nDatabase ready.")
        print(f"  Applied: {applied_count}  Skipped: {skipped}")
        print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
