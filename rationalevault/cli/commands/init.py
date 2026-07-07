import argparse
import sys
import uuid
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("init", help="Initialize a new RationaleVault project in the current directory")
    parser.set_defaults(func=handler)


def handler(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".rationalevault"
    relay_dir.mkdir(parents=True, exist_ok=True)

    protocol_file = relay_dir / "relay_protocol.yaml"
    skill_file = relay_dir / "RELAY_SKILL.md"
    checklist_file = relay_dir / "handoff_checklist.md"
    project_config = relay_dir / "project.yaml"

    # Default Protocol YAML
    if not protocol_file.exists():
        protocol_file.write_text("""name: "RationaleVault Project"
version: "1.0"
description: "Rules for agent behavior in this repository."
execution_priority:
  - "OPEN_QUESTION"
  - "BLOCKER"
  - "TASK"
  - "DECISION"
rules:
  - id: "resolve_questions_first"
    description: "Always address open questions blocking active tasks before starting new work."
    severity: "error"
  - id: "respect_accepted_decisions"
    description: "Do not reverse accepted decisions without a DECISION_SUPERSEDED event."
    severity: "error"
""", encoding="utf-8")

    # Default Skill MD
    if not skill_file.exists():
        skill_file.write_text("""# RationaleVault Agent Skill Protocol
* **Authoritative Memory**: Rely only on the RationaleVault Context Block.
* **Question-First**: Resolve open questions before starting new tasks.
* **Decision Protection**: Do not reverse accepted decisions.
""", encoding="utf-8")

    # Default Handoff Checklist
    if not checklist_file.exists():
        checklist_file.write_text("""# RationaleVault Handoff Checklist
- What changed?
- What decisions were made?
- What questions were resolved?
- What tasks were completed?
- What should happen next?
""", encoding="utf-8")

    # Project UUID Config & Storage Setup
    if not project_config.exists():
        pid = uuid.uuid4()
        project_config.write_text(f"""project_id: {pid}
protocol_version: 1
storage:
  backend: sqlite
  database: .relay/relay.db
""", encoding="utf-8")

    # Force creation of sqlite schema if not present
    from rationalevault.db.sqlite_store import SQLiteEventStore
    SQLiteEventStore(db_path=str(relay_dir / "rationalevault.db"))

    print(f"[SUCCESS] Bootstrapped RationaleVault configuration in: {relay_dir.relative_to(project_root)}")
