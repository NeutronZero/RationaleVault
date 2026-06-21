-- Relay V1 — Initial Schema
-- Migration: 0001_initial.sql
--
-- Creates the relay_events ledger table and the relay_migrations tracking table.
--
-- ORDERING GUARANTEE:
--   event_sequence (BIGSERIAL) is the PRIMARY KEY and the ONLY authoritative
--   replay ordering key. All reducers MUST use ORDER BY event_sequence ASC.
--
--   version is a per-project monotonic counter assigned by the application
--   (via advisory lock). It exists ONLY for optimistic concurrency control.
--   NEVER use version for replay ordering.
--
-- PROJECT BOOTSTRAP REQUIREMENT:
--   Every project stream MUST begin with these events in order:
--     PROJECT_CREATED → PROJECT_GOAL_SET → PROJECT_FOCUS_CHANGED
--   compile_cognitive_head() raises MissingProjectBootstrapError if violated.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Event Ledger ─────────────────────────────────────────────────────────────

CREATE TABLE relay_events (
    -- Global monotonic ordering key. Assigned by PostgreSQL (BIGSERIAL).
    -- Replay ALWAYS orders by: ORDER BY event_sequence ASC
    event_sequence  BIGSERIAL                   NOT NULL,

    -- Stable external reference UUID for cross-linking (parent_id, audit, etc.)
    id              UUID                        NOT NULL DEFAULT uuid_generate_v4(),

    -- Which project this event belongs to
    project_id      UUID                        NOT NULL,

    -- Logical sub-stream grouping within a project.
    -- Examples: 'main', 'tasks', 'decisions', 'questions', 'knowledge', 'metrics'
    -- Reducers load ALL streams; stream_id is for targeted queries only.
    stream_id       TEXT                        NOT NULL DEFAULT 'main',

    -- Per-project monotonic counter.
    -- Assigned by application under advisory lock.
    -- Used ONLY for optimistic concurrency — NOT for replay order.
    version         BIGINT                      NOT NULL,

    -- Event type (must match EventType enum in relay/schema/events.py)
    event_type      TEXT                        NOT NULL,

    -- Structured metadata envelope
    -- JSON schema: { actor, source, correlation_id, session_id }
    metadata        JSONB                       NOT NULL DEFAULT '{}',

    -- Event-specific payload. Schema varies by event_type.
    -- See reducer docstrings for expected fields per event type.
    payload         JSONB                       NOT NULL DEFAULT '{}',

    -- Optional reference to the event that caused this one.
    -- Useful for tracing chains of events across agents.
    parent_id       UUID                        REFERENCES relay_events(id) ON DELETE SET NULL,

    -- Wall-clock insertion time, set by PostgreSQL.
    -- Do NOT use for replay ordering. Use event_sequence instead.
    recorded_at     TIMESTAMPTZ                 NOT NULL DEFAULT now(),

    -- ── Constraints ───────────────────────────────────────────────────────
    PRIMARY KEY (event_sequence),
    UNIQUE (id),
    UNIQUE (project_id, version)   -- optimistic concurrency guard
);

COMMENT ON TABLE relay_events IS
    'Relay immutable event ledger. Append-only. Never UPDATE or DELETE rows.';

COMMENT ON COLUMN relay_events.event_sequence IS
    'Global monotonic ordering key (BIGSERIAL). ALWAYS use ORDER BY event_sequence ASC for replay. This is the source of truth for event ordering.';

COMMENT ON COLUMN relay_events.version IS
    'Per-project monotonic counter. Used for optimistic concurrency only. NOT the replay ordering key.';

COMMENT ON COLUMN relay_events.stream_id IS
    'Logical sub-stream grouping. Reducers load all streams. Use for targeted queries only.';

-- ── Migration Tracking ────────────────────────────────────────────────────────

CREATE TABLE relay_migrations (
    filename    TEXT        PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE relay_migrations IS
    'Tracks applied SQL migrations. Managed by scripts/init_db.py.';
