from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any


def parse_markdown_session(md_content: str) -> dict[str, Any]:
    goal = ""
    tasks = []
    decisions = []
    rationales = []
    questions = []
    blockers = []

    current_section = None
    lines = md_content.splitlines()

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue

        # Check section header
        header_match = re.match(r"^#\s+(Goal|Tasks|Decisions|Questions|Blockers)", line, re.IGNORECASE)
        if header_match:
            current_section = header_match.group(1).lower()
            continue

        if current_section == "goal":
            goal += (line_strip + " ")
        elif current_section == "tasks" and (line_strip.startswith("-") or line_strip.startswith("*")):
            tasks.append(re.sub(r"^[-*]\s+", "", line_strip))
        elif current_section == "decisions" and (line_strip.startswith("-") or line_strip.startswith("*")):
            text = re.sub(r"^[-*]\s+", "", line_strip)
            # Rationale parser
            if ". rationale: " in text.lower():
                parts = re.split(r"\. Rationale: ", text, flags=re.IGNORECASE)
                decisions.append(parts[0])
                rationales.append(parts[1])
            else:
                decisions.append(text)
        elif current_section == "questions" and (line_strip.startswith("-") or line_strip.startswith("*")):
            questions.append(re.sub(r"^[-*]\s+", "", line_strip))
        elif current_section == "blockers" and (line_strip.startswith("-") or line_strip.startswith("*")):
            blockers.append(re.sub(r"^[-*]\s+", "", line_strip))

    return {
        "goal": goal.strip(),
        "tasks": tasks,
        "decisions": decisions,
        "rationales": rationales,
        "questions": questions,
        "blockers": blockers,
    }


def main() -> None:
    project_root = Path.cwd()
    raw_dir = project_root / "rationalevault" / "evaluation" / "handoff_cases" / "real_agents" / "raw"
    processed_dir = project_root / "rationalevault" / "evaluation" / "handoff_cases" / "real_agents" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    if not raw_dir.exists():
        print(f"Raw directory does not exist: {raw_dir}")
        return

    sessions = []
    agent_pair_counts = {}

    for session_path in raw_dir.iterdir():
        if not session_path.is_dir():
            continue

        metadata_file = session_path / "session_metadata.json"
        if not metadata_file.exists():
            continue

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        session_id = metadata["session_id"]
        agents = metadata.get("agents") or []

        # Track agent transition pairs
        for i in range(1, len(agents)):
            pair = f"{agents[i-1]}->{agents[i]}"
            agent_pair_counts[pair] = agent_pair_counts.get(pair, 0) + 1

        # Parse md handoff files
        goal = ""
        tasks = []
        decisions = []
        rationales = []
        questions = []
        blockers = []

        md_files = sorted(list(session_path.glob("handoff_*.md")))
        for mdf in md_files:
            with open(mdf, "r", encoding="utf-8") as f:
                content = f.read()
            parsed = parse_markdown_session(content)
            if parsed["goal"]:
                goal = parsed["goal"]
            tasks.extend(parsed["tasks"])
            decisions.extend(parsed["decisions"])
            rationales.extend(parsed["rationales"])
            questions.extend(parsed["questions"])
            blockers.extend(parsed["blockers"])

        # Create structured HandoffBenchmark JSON
        benchmark = {
            "benchmark_id": f"real_{session_id}",
            "benchmark_type": "real_world",
            "benchmark_version": 1,
            "expected_goal": goal,
            "expected_tasks": list(set(tasks)),
            "expected_decisions": list(set(decisions)),
            "expected_questions": list(set(questions)),
            "expected_blockers": list(set(blockers)),
            "expected_next_action": tasks[0] if tasks else "Done",
            "handoff_chain": agents,
            "metadata": {
                "session_id": session_id,
                "expected_rationales": list(set(rationales)),
            }
        }

        out_path = processed_dir / f"{session_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(benchmark, f, indent=2)

        sessions.append({
            "session_id": session_id,
            "handoffs": len(agents) - 1 if len(agents) > 1 else 0,
            "agents": agents,
        })

    # Write manifest
    manifest = {
        "corpus_version": 1,
        "generated_at": time.asctime(),
        "sessions_count": len(sessions),
        "total_handoffs": sum(s["handoffs"] for s in sessions),
        "agent_pair_counts": agent_pair_counts,
        "sessions": sessions,
    }

    manifest_path = project_root / "rationalevault" / "evaluation" / "handoff_cases" / "real_agents" / "corpus_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Corpus Builder complete. Processed {len(sessions)} session(s).")


if __name__ == "__main__":
    main()
