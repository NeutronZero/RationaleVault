"""
Record OpenCode's work into Relay event store.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from relay.db.event_store import EventStore
from relay.schema.events import EventMetadata, EventType


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True, help="UUID of the project")
    args = parser.parse_args()

    pid = uuid.UUID(args.project_id)
    store = EventStore()
    opencode = EventMetadata(actor="OpenCode", source="manual",
                             session_id="opencode_session_001",
                             correlation_id="validation_corr_002")

    # DECISION_PROPOSED: Use SQLite
    store.append_event(pid, "decisions", EventType.DECISION_PROPOSED, {
        "decision_id": "dec_02",
        "title": "Use SQLite as database",
        "description": "Store API data locally in an SQLite database file for simple, single-file serverless operation.",
        "rationale": "SQLite satisfies the low complexity requirement for a simple TODO API validation.",
    }, opencode)
    print("OK: DECISION_PROPOSED: Use SQLite")

    # DECISION_ACCEPTED: Use SQLite
    store.append_event(pid, "decisions", EventType.DECISION_ACCEPTED, {
        "decision_id": "dec_02",
    }, opencode)
    print("OK: DECISION_ACCEPTED: Use SQLite")

    # OPEN_QUESTION_RESOLVED: SQLite or PostgreSQL? (q_01)
    store.append_event(pid, "questions", EventType.OPEN_QUESTION_RESOLVED, {
        "question_id": "q_01",
        "resolution": "SQLite selected for its simplicity and ease of setup in validation environment.",
    }, opencode)
    print("OK: OPEN_QUESTION_RESOLVED: q_01")

    # TASK_MUTATED: Update task_02 to show it's unblocked (although compiler does this, it's good practice)
    store.append_event(pid, "tasks", EventType.TASK_MUTATED, {
        "task_id": "task_02",
        "blocked_by": [],
    }, opencode)
    print("OK: TASK_MUTATED: task_02")


if __name__ == "__main__":
    main()
