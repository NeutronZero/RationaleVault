"""
Relay Command Line Interface (CLI) Entry Point.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from relay.db.connection import get_connection


def cmd_init(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".relay"
    relay_dir.mkdir(parents=True, exist_ok=True)

    protocol_file = relay_dir / "relay_protocol.yaml"
    skill_file = relay_dir / "RELAY_SKILL.md"
    checklist_file = relay_dir / "handoff_checklist.md"
    project_config = relay_dir / "project.yaml"

    # Default Protocol YAML
    if not protocol_file.exists():
        protocol_file.write_text("""name: "Relay Project"
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
        skill_file.write_text("""# Relay Agent Skill Protocol
* **Authoritative Memory**: Rely only on the Relay Context Block.
* **Question-First**: Resolve open questions before starting new tasks.
* **Decision Protection**: Do not reverse accepted decisions.
""", encoding="utf-8")

    # Default Handoff Checklist
    if not checklist_file.exists():
        checklist_file.write_text("""# Relay Handoff Checklist
- What changed?
- What decisions were made?
- What questions were resolved?
- What tasks were completed?
- What should happen next?
""", encoding="utf-8")

    # Project UUID Config
    if not project_config.exists():
        pid = uuid.uuid4()
        project_config.write_text(f"""project_id: {pid}
protocol_version: 1
""", encoding="utf-8")

    print(f"[SUCCESS] Bootstrapped Relay configuration in: {relay_dir.relative_to(project_root)}")


def cmd_install(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".relay"
    
    if not relay_dir.exists():
        print("Error: Relay has not been initialized. Run 'relay init' first.")
        sys.exit(1)

    platform = args.platform.lower()
    skill_file = relay_dir / "RELAY_SKILL.md"
    skill_text = skill_file.read_text(encoding="utf-8") if skill_file.exists() else "Default Relay Skill"

    if platform == "claude":
        target = project_root / "CLAUDE.md"
        target.write_text(f"# Claude Code Rules\n\n{skill_text}", encoding="utf-8")
        print(f"[SUCCESS] Installed Claude Code adapter in: {target.relative_to(project_root)}")
    elif platform == "cursor":
        rules_dir = project_root / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        target = rules_dir / "relay.mdc"
        target.write_text(f"# Cursor Custom Rules\n\n{skill_text}", encoding="utf-8")
        print(f"[SUCCESS] Installed Cursor adapter in: {target.relative_to(project_root)}")
    elif platform == "opencode":
        target = project_root / "AGENTS.md"
        target.write_text(f"# OpenCode Rules\n\n{skill_text}", encoding="utf-8")
        print(f"[SUCCESS] Installed OpenCode adapter in: {target.relative_to(project_root)}")
    elif platform == "copilot":
        target = project_root / "copilot-instructions.md"
        target.write_text(f"# Copilot Instructions\n\n{skill_text}", encoding="utf-8")
        print(f"[SUCCESS] Installed Copilot adapter in: {target.relative_to(project_root)}")
    else:
        print(f"Error: Unknown platform '{args.platform}'. Supported: claude, cursor, opencode, copilot.")
        sys.exit(1)


def cmd_uninstall(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".relay"

    # Remove rule files in root
    for file_name in ["CLAUDE.md", "AGENTS.md", "copilot-instructions.md"]:
        p = project_root / file_name
        if p.exists():
            p.unlink()
            print(f"Removed {file_name}")

    # Remove cursor rules
    cursor_rules = project_root / ".cursor" / "rules" / "relay.mdc"
    if cursor_rules.exists():
        cursor_rules.unlink()
        print("Removed .cursor/rules/relay.mdc")

    # Remove .relay dir
    if relay_dir.exists():
        import shutil
        shutil.rmtree(relay_dir)
        print("Removed .relay/ configuration directory.")

    print("[SUCCESS] Relay has been uninstalled from this project.")


def cmd_doctor(args: argparse.Namespace) -> None:
    print("Relay Doctor diagnostics:")
    
    # 1. Environment and database check
    print("Checking database connection...")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                db_ver = cur.fetchone()
                ver_str = list(db_ver.values())[0] if db_ver else "Unknown"
                print(f"  [PASS] Connected to PostgreSQL: {ver_str.strip()[:60]}...")
                
                # Check tables
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
                tables = [row['table_name'] for row in cur.fetchall()]
                print(f"  [INFO] Public tables: {', '.join(tables)}")
                if "relay_events" in tables:
                    print("  [PASS] relay_events table exists.")
                else:
                    print("  [FAIL] relay_events table is missing! Run scripts/init_db.py")
    except Exception as ex:
        print(f"  [FAIL] Database connection failed: {ex}")

    # 2. Local config check
    relay_dir = Path.cwd() / ".relay"
    if relay_dir.exists():
        print(f"  [PASS] Local configuration directory exists: {relay_dir}")
        for config in ["relay_protocol.yaml", "RELAY_SKILL.md", "project.yaml"]:
            if (relay_dir / config).exists():
                print(f"    [PASS] Config file '{config}' exists.")
            else:
                print(f"    [FAIL] Config file '{config}' is missing!")
    else:
        print("  [INFO] Local configuration directory (.relay/) not found. Run 'relay init'")


def cmd_generate_adapters(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".relay"
    
    if not relay_dir.exists():
        print("Error: Relay has not been initialized. Run 'relay init' first.")
        sys.exit(1)

    skill_file = relay_dir / "RELAY_SKILL.md"
    skill_text = skill_file.read_text(encoding="utf-8") if skill_file.exists() else ""

    adapters_dir = relay_dir / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)

    # Compile Claude Adapter
    (adapters_dir / "CLAUDE.md").write_text(f"# Claude Code Instructions\n\n{skill_text}", encoding="utf-8")
    # Compile Cursor Adapter
    (adapters_dir / "cursor_rules.md").write_text(f"# Cursor Instructions\n\n{skill_text}", encoding="utf-8")
    # Compile Copilot Adapter
    (adapters_dir / "copilot-instructions.md").write_text(f"# Copilot Instructions\n\n{skill_text}", encoding="utf-8")
    # Compile OpenCode Adapter
    (adapters_dir / "opencode_instructions.md").write_text(f"# OpenCode Instructions\n\n{skill_text}", encoding="utf-8")

    print(f"[SUCCESS] Compiled adapters in: {adapters_dir.relative_to(project_root)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Relay Multi-Agent Memory Layer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    subparsers.add_parser("init", help="Initialize Relay in the current project directory")

    # install
    parser_install = subparsers.add_parser("install", help="Install platform adapters")
    parser_install.add_argument("--platform", required=True, help="Target platform (claude, cursor, opencode, copilot)")

    # uninstall
    subparsers.add_parser("uninstall", help="Uninstall Relay adapters and configs from current project")

    # doctor
    subparsers.add_parser("doctor", help="Check diagnostics and system status")

    # generate-adapters
    subparsers.add_parser("generate-adapters", help="Recompile adapter templates")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "install":
        cmd_install(args)
    elif args.command == "uninstall":
        cmd_uninstall(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "generate-adapters":
        cmd_generate_adapters(args)


if __name__ == "__main__":
    main()
