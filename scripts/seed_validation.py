"""
Relay Validation Seeder — seeds the stage 1 validation events for the TODO API.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from rationalevault.db.event_store import EventStore
from rationalevault.cognitive_head.compiler import compile_cognitive_head
from rationalevault.compilers.claude import ClaudeCompiler
from rationalevault.schema.events import EventMetadata, EventType


def _meta(actor: str, source: str = "seed_validation",
          session: str = "validation_session_001") -> EventMetadata:
    return EventMetadata(actor=actor, source=source,
                         session_id=session, correlation_id="validation_corr_001")


def seed_validation() -> uuid.UUID:
    store = EventStore()
    pid = uuid.uuid4()
    human = _meta("Human")
    claude = _meta("Antigravity")

    print(f"\n[SEED] Seeding Validation Project: Relay Validation")
    print(f"   ID: {pid}\n")

    # PROJECT_CREATED
    store.append_event(pid, "main", EventType.PROJECT_CREATED, {
        "name": "Relay Validation",
        "description": "Validate that Relay can preserve project continuity across agent switches without manual summaries.",
    }, human)
    print("OK: PROJECT_CREATED")

    # PROJECT_GOAL_SET
    store.append_event(pid, "main", EventType.PROJECT_GOAL_SET, {
        "goal": "Validate that Relay can preserve project continuity across agent switches without manual summaries.",
    }, human)
    print("OK: PROJECT_GOAL_SET")

    # PROJECT_FOCUS_CHANGED
    store.append_event(pid, "main", EventType.PROJECT_FOCUS_CHANGED, {
        "focus": "Build a simple TODO API",
    }, human)
    print("OK: PROJECT_FOCUS_CHANGED")

    # DECISION_PROPOSED & ACCEPTED: Use FastAPI
    store.append_event(pid, "decisions", EventType.DECISION_PROPOSED, {
        "decision_id": "dec_01",
        "title": "Use FastAPI for TODO API",
        "description": "FastAPI provides automatic OpenAPI docs, fast execution, and easy Pydantic schema validation.",
        "rationale": "FastAPI is the standard choice for modern Python web APIs.",
    }, claude)
    store.append_event(pid, "decisions", EventType.DECISION_ACCEPTED,
                       {"decision_id": "dec_01"}, human)
    print("OK: DECISION_ACCEPTED: Use FastAPI")

    # TASK_CREATED: Design API schema
    store.append_event(pid, "tasks", EventType.TASK_CREATED, {
        "task_id": "task_01",
        "title": "Design API schema",
        "description": "Define the endpoints and schemas for TODO items.",
        "priority": "high",
        "tags": ["design"],
    }, claude)
    print("OK: TASK_CREATED: Design API schema")

    # TASK_CREATED: Create database layer
    store.append_event(pid, "tasks", EventType.TASK_CREATED, {
        "task_id": "task_02",
        "title": "Create database layer",
        "description": "Initialize database connection and models.",
        "priority": "high",
        "tags": ["database"],
        "blocked_by": ["q_01"],
    }, claude)
    print("OK: TASK_CREATED: Create database layer")

    # OPEN_QUESTION_RAISED: Use SQLite or PostgreSQL?
    store.append_event(pid, "questions", EventType.OPEN_QUESTION_RAISED, {
        "question_id": "q_01",
        "title": "SQLite or PostgreSQL?",
        "description": "Should we use SQLite for simplicity or PostgreSQL for robust persistence?",
        "priority": "high",
        "blocks_task_ids": ["task_02"],
    }, claude)
    print("OK: OPEN_QUESTION_RAISED: SQLite or PostgreSQL?")

    count = store.get_event_count(pid)
    print(f"\nTotal events seeded: {count}")
    return pid


def main() -> None:
    project_id = seed_validation()

    print("\n" + "=" * 60)
    print("Compiling Cognitive Head...")
    store = EventStore()
    head = compile_cognitive_head(project_id, store=store)

    print(f"\nCognitive Head:")
    print(f"   Project:      {head.project_name}")
    print(f"   Ledger v:     {head.ledger_version}")
    print(f"   Active Tasks: {len(head.active_tasks)}")
    print(f"   Decisions:    {len(head.active_decisions)}")
    print(f"   Open Qs:      {len(head.open_questions)}")
    print(f"   Blockers:     {len(head.blockers)}")

    print("\n" + "=" * 60)
    print("Claude Context Block (paste this into OpenCode):")
    print("=" * 60 + "\n")
    compiler = ClaudeCompiler()
    print(compiler.compile(head))
    print("\n" + "=" * 60)
    print(f"\n[SUCCESS] Done. Project ID: {project_id}")


if __name__ == "__main__":
    main()
