-- Relay V1.4 — Snapshot Store
-- Migration: 0003_snapshots.sql
--
-- Adds the relay_snapshots table for durable projection caching.
-- Snapshots allow compile_cognitive_head() to replay only delta events
-- instead of the full ledger, reducing O(N) to O(delta).
--
-- DESIGN:
--   One snapshot per (project_id, projection_name) pair.
--   Retrieved by ORDER BY sequence DESC LIMIT 1.
--   No UNIQUE constraint — historical snapshots are retained for audit.
--
-- See ADR-026 for full design rationale.

-- ── SQLite ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rationalevault_snapshots (
    id                TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
    project_id        TEXT NOT NULL,
    projection_name   TEXT NOT NULL,
    sequence          INTEGER NOT NULL,
    payload           TEXT NOT NULL,
    schema_version    INTEGER NOT NULL DEFAULT 1,
    projection_version INTEGER NOT NULL DEFAULT 1,
    snapshot_hash     TEXT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_snapshots_lookup
    ON rationalevault_snapshots (project_id, projection_name, sequence DESC);

-- ── PostgreSQL ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS relay_snapshots (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID NOT NULL,
    projection_name   TEXT NOT NULL,
    sequence          BIGINT NOT NULL,
    payload           JSONB NOT NULL,
    schema_version    INTEGER NOT NULL DEFAULT 1,
    projection_version INTEGER NOT NULL DEFAULT 1,
    snapshot_hash     TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_relay_snapshots_lookup
    ON relay_snapshots (project_id, projection_name, sequence DESC);

COMMENT ON TABLE relay_snapshots IS
    'RationaleVault projection snapshot cache. Stores point-in-time captures of compiled projections to avoid full event replay.';
