-- Relay V1 — Performance Indexes
-- Migration: 0002_indexes.sql
--
-- Applied after 0001_initial.sql.
--
-- Index strategy:
--   - Primary retrieval pattern: all events for a project, event_sequence ASC
--   - Secondary: events for a specific sub-stream within a project
--   - Tertiary: event_type filtering (audit, knowledge stubs)
--   - GIN index on metadata JSONB for actor/session queries

-- Primary retrieval: all events for a project in event_sequence order.
-- Used by get_project_stream() and compile_cognitive_head().
CREATE INDEX idx_relay_events_project_sequence
    ON relay_events (project_id, event_sequence ASC);

-- Sub-stream retrieval: events for a specific stream within a project.
-- Used by get_stream() for targeted queries.
CREATE INDEX idx_relay_events_project_stream_sequence
    ON relay_events (project_id, stream_id, event_sequence ASC);

-- Event type filtering: useful for audit queries and knowledge stub analysis.
CREATE INDEX idx_relay_events_event_type
    ON relay_events (event_type);

-- Temporal queries: find recent events across all projects.
CREATE INDEX idx_relay_events_recorded_at
    ON relay_events (recorded_at DESC);

-- Metadata actor/session filtering: "all events written by Claude in session X"
-- GIN index supports JSONB containment queries (@>) efficiently.
CREATE INDEX idx_relay_events_metadata_gin
    ON relay_events USING gin (metadata);

-- Parent tracking: follow event causality chains.
CREATE INDEX idx_relay_events_parent_id
    ON relay_events (parent_id)
    WHERE parent_id IS NOT NULL;
