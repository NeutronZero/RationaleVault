from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_corpus_manifest_and_processed_files() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    manifest_path = project_root / "relay" / "evaluation" / "handoff_cases" / "real_agents" / "corpus_manifest.json"
    processed_dir = project_root / "relay" / "evaluation" / "handoff_cases" / "real_agents" / "processed"

    # Verify manifest exists and has correct version
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["corpus_version"] == 1
    assert manifest["sessions_count"] == 2
    assert "claude->opencode" in manifest["agent_pair_counts"]

    # Verify processed JSON files exist and have versioning and rationales
    p1 = processed_dir / "session_001.json"
    p2 = processed_dir / "session_002.json"
    assert p1.exists()
    assert p2.exists()

    with open(p1, "r", encoding="utf-8") as f:
        bench = json.load(f)
    assert bench["benchmark_version"] == 1
    assert "expected_rationales" in bench["metadata"]
    assert len(bench["metadata"]["expected_rationales"]) == 1


def test_run_handoff_suite_with_corpus() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    runner_path = project_root / "relay" / "evaluation" / "run_handoff_suite.py"

    res = subprocess.run(
        [sys.executable, str(runner_path)],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    assert res.returncode == 0
    assert "Rationale Recall:" in res.stdout
