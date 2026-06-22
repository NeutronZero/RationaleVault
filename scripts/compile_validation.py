"""
Compile Cognitive Head for the validation project and output the context block.
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True, help="UUID of the project")
    args = parser.parse_args()

    pid = uuid.UUID(args.project_id)
    store = EventStore()
    head = compile_cognitive_head(pid, store=store)

    print("\n" + "=" * 60)
    print("Compiling Cognitive Head...")
    print(f"\nCognitive Head:")
    print(f"   Project:      {head.project_name}")
    print(f"   Ledger v:     {head.ledger_version}")
    print(f"   Active Tasks: {len(head.active_tasks)}")
    print(f"   Decisions:    {len(head.active_decisions)}")
    print(f"   Open Qs:      {len(head.open_questions)}")
    print(f"   Blockers:     {len(head.blockers)}")

    print("\n" + "=" * 60)
    print("Claude Context Block (paste this into Antigravity):")
    print("=" * 60 + "\n")
    compiler = ClaudeCompiler()
    print(compiler.compile(head))
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
