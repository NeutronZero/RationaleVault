"""
Relay Handoff Metrics — Day 1 continuity measurement tool.

Measures how well an incoming agent preserved Relay context across a handoff.
Use this immediately after pasting a Relay Context Block into a new agent.

Metrics (per design freeze, Change 7):
  1. Context Load Time         — seconds from paste to agent's first response
  2. Task Continuity           — % of active tasks correctly identified by agent
  3. Decision Recall           — % of accepted decisions the agent referenced
  4. Question Recall           — % of open questions the agent identified
  5. Time to Productive Action — seconds to first CORRECT next-step action

All metrics are recorded back to the Relay ledger as FACT_RECORDED events
so they accumulate across Sprint C experiments.

Usage:
    python scripts/handoff_metrics.py --project-id <UUID>
    python scripts/handoff_metrics.py --project-id <UUID> --agent "ChatGPT"
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from relay.db.event_store import EventStore
from relay.cognitive_head.compiler import compile_cognitive_head
from relay.schema.events import EventMetadata, EventType


def _recall_score(ground_truth: list[str], agent_identified: list[str]) -> float:
    """
    Calculate partial recall: what fraction of ground truth did the agent identify?

    Uses substring matching so "psycopg3" matches "Use psycopg3 sync".
    Returns 1.0 if ground_truth is empty (nothing to recall).
    """
    if not ground_truth:
        return 1.0
    gt_lower = [s.lower() for s in ground_truth]
    ai_lower = [s.lower() for s in agent_identified]
    matched = sum(
        1 for gt in gt_lower
        if any(gt in ai or ai in gt for ai in ai_lower)
    )
    return matched / len(gt_lower)


def _prompt_items(items: list[str], label: str) -> list[str]:
    """Interactively prompt the user to select which items the agent identified."""
    if not items:
        return []
    print(f"\n  Ground truth {label} ({len(items)}):")
    for i, item in enumerate(items, 1):
        print(f"    {i}. {item}")
    print(f"\n  Which {label} did the agent identify?")
    print("  (Enter item numbers separated by commas, 'all', or 'none')")
    raw = input("  > ").strip().lower()

    if raw == "all":
        return items
    if raw == "none" or raw == "":
        return []

    try:
        indices = [int(x.strip()) - 1 for x in raw.split(",")]
        return [items[i] for i in indices if 0 <= i < len(items)]
    except (ValueError, IndexError):
        # Fall back to treating input as literal text items
        return [x.strip() for x in raw.split(",")]


def run_measurement(project_id: UUID, agent_name: str) -> None:
    print("\n" + "=" * 60)
    print(f"🔁 Relay Handoff Metrics")
    print(f"   Incoming agent: {agent_name}")
    print("=" * 60)

    store = EventStore()
    head = compile_cognitive_head(project_id, store=store)

    print(f"\nProject:       {head.project_name}")
    print(f"Ledger v:      {head.ledger_version}")
    print(f"Active Tasks:  {len(head.active_tasks)}")
    print(f"Decisions:     {len(head.active_decisions)}")
    print(f"Open Qs:       {len(head.open_questions)}")

    # ── Metric 1: Context Load Time ─────────────────────────────────────────
    print("\n" + "─" * 60)
    print("METRIC 1: Context Load Time")
    print("─" * 60)
    input("\nPress ENTER the moment you paste the Relay context block into the agent...")
    t_paste = time.time()
    input("Press ENTER the moment the agent produces its FIRST response...")
    context_load_time = time.time() - t_paste
    print(f"  → Context Load Time: {context_load_time:.1f}s")

    # ── Metric 5: Time to Productive Action ─────────────────────────────────
    print("\n" + "─" * 60)
    print("METRIC 5: Time to Productive Action")
    print("─" * 60)
    print("  (Wait until the agent produces its first CORRECT next-step action.)")
    input("\nPress ENTER when the agent produces its first correct action...")
    time_to_productive = time.time() - t_paste
    print(f"  → Time to Productive Action: {time_to_productive:.1f}s")

    # ── Metric 2: Task Continuity ────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("METRIC 2: Task Continuity")
    print("─" * 60)
    gt_tasks = [t.title for t in head.active_tasks]
    agent_tasks = _prompt_items(gt_tasks, "active tasks")
    task_recall = _recall_score(gt_tasks, agent_tasks)
    print(f"  → Task Continuity: {task_recall:.0%} ({len(agent_tasks)}/{len(gt_tasks)} identified)")

    # ── Metric 3: Decision Recall ────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("METRIC 3: Decision Recall")
    print("─" * 60)
    gt_decisions = [d.title for d in head.active_decisions]
    agent_decisions = _prompt_items(gt_decisions, "accepted decisions")
    decision_recall = _recall_score(gt_decisions, agent_decisions)
    print(f"  → Decision Recall: {decision_recall:.0%} ({len(agent_decisions)}/{len(gt_decisions)} referenced)")

    # ── Metric 4: Question Recall ─────────────────────────────────────────
    print("\n" + "─" * 60)
    print("METRIC 4: Question Recall")
    print("─" * 60)
    gt_questions = [q.title for q in head.open_questions]
    agent_questions = _prompt_items(gt_questions, "open questions")
    question_recall = _recall_score(gt_questions, agent_questions)
    print(f"  → Question Recall: {question_recall:.0%} ({len(agent_questions)}/{len(gt_questions)} identified)")

    # ── Summary ───────────────────────────────────────────────────────────────
    overall = (task_recall + decision_recall + question_recall) / 3

    print("\n" + "=" * 60)
    print("📊 HANDOFF METRICS SUMMARY")
    print("=" * 60)
    print(f"  Agent:                     {agent_name}")
    print(f"  Ledger Version:            {head.ledger_version}")
    print(f"  Context Load Time:         {context_load_time:.1f}s")
    print(f"  Time to Productive Action: {time_to_productive:.1f}s")
    print(f"  Task Continuity:           {task_recall:.0%}")
    print(f"  Decision Recall:           {decision_recall:.0%}")
    print(f"  Question Recall:           {question_recall:.0%}")
    print(f"  Overall Recall:            {overall:.0%}")
    print("=" * 60)

    # ── Record metrics to Relay ───────────────────────────────────────────────
    meta = EventMetadata(
        actor="handoff_metrics",
        source="handoff_metrics.py",
        session_id=f"metrics_{uuid.uuid4().hex[:8]}",
        correlation_id="handoff_experiment",
    )
    store.append_event(
        project_id,
        "metrics",
        EventType.FACT_RECORDED,
        {
            "fact_id": f"hm_{uuid.uuid4().hex[:8]}",
            "content": (
                f"Handoff to {agent_name} at ledger v{head.ledger_version}: "
                f"load={context_load_time:.1f}s, productive={time_to_productive:.1f}s, "
                f"tasks={task_recall:.0%}, decisions={decision_recall:.0%}, "
                f"questions={question_recall:.0%}, overall={overall:.0%}"
            ),
            "confidence": "human_confirmed",
            "metrics": {
                "agent": agent_name,
                "ledger_version": head.ledger_version,
                "context_load_time_s": round(context_load_time, 1),
                "time_to_productive_action_s": round(time_to_productive, 1),
                "task_continuity": round(task_recall, 3),
                "decision_recall": round(decision_recall, 3),
                "question_recall": round(question_recall, 3),
                "overall_recall": round(overall, 3),
            },
        },
        meta,
    )
    print(f"\n✅ Metrics recorded to Relay ledger (project {project_id}).")
    print(f"   Run again after next handoff to compare across agents.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure Relay handoff continuity metrics."
    )
    parser.add_argument(
        "--project-id", required=True,
        help="Project UUID to measure (from seed_demo.py output)."
    )
    parser.add_argument(
        "--agent", default="Unknown",
        help="Name of the incoming agent (e.g. 'ChatGPT', 'Hermes')."
    )
    args = parser.parse_args()

    try:
        project_id = UUID(args.project_id)
    except ValueError:
        print(f"Error: '{args.project_id}' is not a valid UUID.")
        sys.exit(1)

    run_measurement(project_id, agent_name=args.agent)


if __name__ == "__main__":
    main()
