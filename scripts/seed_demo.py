"""
Relay Demo Seeder — creates a realistic project for Sprint C experiment.

Seeds a project with 20+ events covering:
  - Project bootstrap (PROJECT_CREATED, PROJECT_GOAL_SET, PROJECT_FOCUS_CHANGED)
  - Accepted architectural decisions
  - Completed Sprint A + B tasks
  - Open Sprint C tasks
  - Open questions (with blockers)
  - Knowledge stubs (FACT_RECORDED)

After seeding, compiles and prints the Relay Context Block for Claude.

Usage:
    python scripts/seed_demo.py
    python scripts/seed_demo.py --project-name "Relay V1"
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


def _meta(actor: str, source: str = "seed_demo",
          session: str = "seed_session_001") -> EventMetadata:
    return EventMetadata(actor=actor, source=source,
                         session_id=session, correlation_id="seed_corr_001")


def seed(project_name: str) -> uuid.UUID:
    store = EventStore()
    pid = uuid.uuid4()
    human = _meta("Human")
    claude = _meta("Claude")

    print(f"\n[SEED] Seeding: {project_name}")
    print(f"   ID: {pid}\n")

    # ── Bootstrap ────────────────────────────────────────────────────────────
    store.append_event(pid, "main", EventType.PROJECT_CREATED, {
        "name": project_name,
        "description": "Event-sourced memory layer for multi-agent AI workflows",
    }, human)
    print("OK: PROJECT_CREATED")

    store.append_event(pid, "main", EventType.PROJECT_GOAL_SET, {
        "goal": (
            "Build a persistent, event-sourced project memory layer that allows any AI agent "
            "(Claude, Cursor, Hermes, ChatGPT, OpenCode) to resume work with full context "
            "continuity within 30 seconds - without manual summarization."
        ),
    }, human)
    print("OK: PROJECT_GOAL_SET")

    store.append_event(pid, "main", EventType.PROJECT_FOCUS_CHANGED, {
        "focus": "Sprint C: running the first real multi-agent handoff experiment",
    }, human)
    print("OK: PROJECT_FOCUS_CHANGED")

    # ── Decisions ────────────────────────────────────────────────────────────
    for decision_id, title, description, rationale in [
        ("dec_01", "Use psycopg3 (sync) instead of asyncpg",
         "V1 workload is local and low-volume. Async complexity is not justified.",
         "Graph-RAG Sprint experience: async DB adds debugging complexity without benefit at small scale."),
        ("dec_02", "No ORM — raw SQL everywhere",
         "Every query must be explicit and auditable for the event ledger.",
         "ORM abstractions hide behavior. Core infrastructure must be fully transparent."),
        ("dec_03", "event_sequence BIGSERIAL is the authoritative replay ordering key",
         "Reducers always use ORDER BY event_sequence ASC. version is only for concurrency.",
         "Prevents subtle ordering bugs if multiple agents write concurrently."),
        ("dec_04", "No Alembic for V1 — plain SQL migrations",
         "migrations/0001_initial.sql + scripts/init_db.py is sufficient.",
         "Too much infrastructure too early slows learning. Add Alembic when needed."),
    ]:
        store.append_event(pid, "decisions", EventType.DECISION_PROPOSED, {
            "decision_id": decision_id,
            "title": title,
            "description": description,
            "rationale": rationale,
        }, claude)
        store.append_event(pid, "decisions", EventType.DECISION_ACCEPTED,
                           {"decision_id": decision_id}, human)
        print(f"OK: DECISION_ACCEPTED: {title[:50]}")

    # ── Completed Sprint A tasks ─────────────────────────────────────────────
    sprint_a_tasks = [
        ("task_01", "Set up PostgreSQL 17 with docker-compose",
         "PostgreSQL 17 + uuid-ossp. Port 5432. Persistent volume.", "high"),
        ("task_02", "Create SQL migrations (0001_initial.sql, 0002_indexes.sql)",
         "event_sequence BIGSERIAL primary ordering. UNIQUE(project_id, version).", "high"),
        ("task_03", "Implement scripts/init_db.py",
         "Idempotent migration runner. Tracks applied migrations in relay_migrations.", "normal"),
        ("task_04", "Implement relay/db/connection.py",
         "psycopg3 sync connection with auto-commit/rollback context manager.", "high"),
        ("task_05", "Implement EventStore.append_event()",
         "Advisory lock for per-project version monotonicity. Returns EventRecord.", "high"),
        ("task_06", "Implement EventStore.get_project_stream() and replay_stream()",
         "Both use ORDER BY event_sequence ASC. since_sequence supported.", "high"),
        ("task_07", "Write 1000-event ordering test",
         "Verify event_sequence ASC, version monotonicity, multi-project isolation.", "high"),
    ]
    for task_id, title, description, priority in sprint_a_tasks:
        store.append_event(pid, "tasks", EventType.TASK_CREATED, {
            "task_id": task_id,
            "title": title,
            "description": description,
            "priority": priority,
            "tags": ["sprint-a"],
        }, claude)
        store.append_event(pid, "tasks", EventType.TASK_COMPLETED,
                           {"task_id": task_id}, claude)
        print(f"OK: TASK_COMPLETED: {title[:50]}")

    # ── Completed Sprint B tasks ─────────────────────────────────────────────
    sprint_b_tasks = [
        ("task_08", "Implement state reducers (Project, Task, Decision, Question)",
         "Pure folds over event lists. Deterministic. No I/O.", "high"),
        ("task_09", "Implement SnapshotStore placeholder interface",
         "V1: all no-ops. Interface frozen so compiler can adopt later.", "normal"),
        ("task_10", "Implement compile_cognitive_head()",
         "Full replay. Bootstrap validation. Priority sort. Blocker derivation.", "high"),
        ("task_11", "Implement ClaudeCompiler",
         "Open Questions first. Priority icons. DO NOT REVERSE warning on decisions.", "high"),
        ("task_12", "Write unit tests (reducers, cognitive head, claude compiler)",
         "Pure tests. No DB required. Determinism verified.", "normal"),
    ]
    for task_id, title, description, priority in sprint_b_tasks:
        store.append_event(pid, "tasks", EventType.TASK_CREATED, {
            "task_id": task_id,
            "title": title,
            "description": description,
            "priority": priority,
            "tags": ["sprint-b"],
        }, claude)
        store.append_event(pid, "tasks", EventType.TASK_COMPLETED,
                           {"task_id": task_id}, claude)
        print(f"OK: TASK_COMPLETED: {title[:50]}")

    # ── Open Sprint C tasks ──────────────────────────────────────────────────
    store.append_event(pid, "tasks", EventType.TASK_CREATED, {
        "task_id": "task_13",
        "title": "Run Sprint C handoff experiment",
        "description": (
            "Generate 20-50 events. Compile Relay Context Block via ClaudeCompiler. "
            "Paste into ChatGPT. Verify continuity. "
            "Then: Claude → Relay → ChatGPT → Relay → Hermes."
        ),
        "priority": "high",
        "tags": ["sprint-c", "experiment"],
    }, human)
    print("OK: TASK_CREATED: Sprint C experiment (OPEN)")

    store.append_event(pid, "tasks", EventType.TASK_CREATED, {
        "task_id": "task_14",
        "title": "Record handoff metrics with scripts/handoff_metrics.py",
        "description": (
            "After each handoff, record: Context Load Time, Task Continuity, "
            "Decision Recall, Question Recall, Time to Productive Action."
        ),
        "priority": "high",
        "tags": ["sprint-c", "metrics"],
        "blocked_by": ["q_02"],
    }, human)
    print("OK: TASK_CREATED: Record metrics (OPEN, blocked by q_02)")

    store.append_event(pid, "tasks", EventType.TASK_CREATED, {
        "task_id": "task_15",
        "title": "Document Sprint C failures and plan Sprint D",
        "description": (
            "After experiment: identify where continuity broke. "
            "Only add Knowledge Compiler, Context Planner, etc. if failures demand them."
        ),
        "priority": "normal",
        "tags": ["sprint-c", "planning"],
        "blocked_by": ["q_01", "q_02"],
    }, human)
    print("OK: TASK_CREATED: Plan Sprint D (OPEN, blocked)")

    # ── Open Questions ────────────────────────────────────────────────────────
    store.append_event(pid, "questions", EventType.OPEN_QUESTION_RAISED, {
        "question_id": "q_01",
        "title": "Should Sprint C use the Relay project itself or a synthetic scenario?",
        "description": (
            "Option A (Dogfood): Use Relay V1 as the test subject. "
            "Richer but harder to score. Risk: we may not have clean ground truth.\n"
            "Option B (Synthetic): Create a fictional project with known state. "
            "Cleaner measurement but artificial.\n"
            "Recommendation: Option A for authenticity, but define scoring criteria first."
        ),
        "priority": "high",
        "blocks_task_ids": ["task_15"],
    }, human)
    print("OK: OPEN_QUESTION_RAISED: Real vs synthetic (HIGH)")

    store.append_event(pid, "questions", EventType.OPEN_QUESTION_RAISED, {
        "question_id": "q_02",
        "title": "What is the baseline 'Time to Productive Action' without Relay?",
        "description": (
            "Before measuring Relay's improvement, we need a baseline measurement. "
            "Without the Relay context block, how long does it take for Claude/ChatGPT/Hermes "
            "to identify the correct next action from scratch on this project? "
            "Run one baseline trial (no context block) before Sprint C proper."
        ),
        "priority": "high",
        "blocks_task_ids": ["task_14", "task_15"],
    }, human)
    print("OK: OPEN_QUESTION_RAISED: Baseline measurement (HIGH)")

    # ── Knowledge stubs ───────────────────────────────────────────────────────
    store.append_event(pid, "knowledge", EventType.FACT_RECORDED, {
        "fact_id": "fact_01",
        "content": (
            "Graph-RAG platform evolved from Sprint 7 through Sprint 23 by adding subsystems "
            "only in response to observed retrieval failures — not from upfront design."
        ),
        "confidence": "human_confirmed",
        "source": "architecture_review",
    }, human)

    store.append_event(pid, "knowledge", EventType.FACT_RECORDED, {
        "fact_id": "fact_02",
        "content": (
            "PostgreSQL advisory locks (pg_advisory_xact_lock) provide sufficient "
            "per-project write serialization at V1 scale without application-level locking."
        ),
        "confidence": "agent_claim",
        "source": "implementation_review",
    }, claude)
    print("OK: FACT_RECORDED: 2 knowledge stubs")

    count = store.get_event_count(pid)
    print(f"\nTotal events seeded: {count}")
    return pid


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a demo Relay project.")
    parser.add_argument("--project-name", default="Relay V1",
                        help="Name for the demo project (default: 'Relay V1').")
    args = parser.parse_args()

    project_id = seed(args.project_name)

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
    print("Claude Context Block (paste this into Claude):")
    print("=" * 60 + "\n")
    compiler = ClaudeCompiler()
    print(compiler.compile(head))
    print("\n" + "=" * 60)
    print(f"\n[SUCCESS] Done. Project ID: {project_id}")
    print(f"   Run Sprint C: python scripts/handoff_metrics.py --project-id {project_id}")


if __name__ == "__main__":
    main()
