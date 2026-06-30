from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from rationalevault.evaluation.benchmark_schema import HandoffBenchmark
from rationalevault.evaluation.continuity_metrics import calculate_recall, calculate_drift, compute_metrics
from rationalevault.evaluation.degradation_metrics import calculate_degradation, calculate_event_rates
from rationalevault.evaluation.failure_taxonomy import FailureAttribution, FailureType


def test_handoff_benchmark_serialization() -> None:
    data = {
        "benchmark_id": "test_id",
        "benchmark_type": "synthetic",
        "expected_goal": "Test goal",
        "expected_tasks": ["Task A", "Task B"],
        "expected_decisions": ["Decision A"],
        "expected_questions": ["Question A"],
        "expected_blockers": ["A blocks B"],
        "expected_next_action": "Task A",
        "handoff_chain": ["agent1", "agent2"],
        "metadata": {"key": "val"},
    }
    benchmark = HandoffBenchmark.from_dict(data)
    assert benchmark.benchmark_id == "test_id"
    assert benchmark.benchmark_type == "synthetic"
    assert benchmark.handoff_chain == ["agent1", "agent2"]
    
    serialized = benchmark.to_dict()
    assert serialized["benchmark_id"] == "test_id"
    assert serialized["metadata"]["key"] == "val"


def test_continuity_metrics() -> None:
    expected = ["Task 1", "Task 2", "Task 3"]
    observed = ["Task 1", "Task 2"]
    # Recall should be 2/3
    assert abs(calculate_recall(expected, observed) - 0.6666) < 0.001

    # Drift should be 0 because observed only contains items from expected
    assert calculate_drift(expected, observed) == 0.0

    # With drift items
    observed_with_drift = ["Task 1", "Task 4"]
    assert calculate_drift(expected, observed_with_drift) == 0.5


def test_degradation_metrics() -> None:
    initial = 1.0
    final = 0.8
    assert abs(calculate_degradation(initial, final, 2) - 0.1) < 1e-9

    rates = calculate_event_rates(100, 85, 5, 10)
    assert rates["human_reject_rate"] == 0.05
    assert rates["human_edit_rate"] == 0.1
    assert rates["auto_accept_rate"] == 0.85


def test_failure_taxonomy() -> None:
    fa = FailureAttribution(
        failure_type=FailureType.TASK_LOSS,
        source_agent="antigravity",
        target_agent="opencode",
        item_id="task_17",
        expected="Task 17 desc",
        observed="Missing",
    )
    d = fa.to_dict()
    assert d["failure_type"] == "TASK_LOSS"
    assert d["source_agent"] == "antigravity"
    assert d["item_id"] == "task_17"


def test_run_handoff_suite_execution() -> None:
    # Run run_handoff_suite.py via subprocess to test exit codes
    project_root = Path(__file__).resolve().parent.parent.parent
    runner_path = project_root / "rationalevault" / "evaluation" / "run_handoff_suite.py"

    # Default run should pass the regression gate (exit code 0)
    result = subprocess.run(
        [sys.executable, str(runner_path)],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    assert result.returncode == 0
    assert "Regression gate validation: PASSED" in result.stdout

    # Simulation with failures should fail the gate (exit code 1)
    result_fail = subprocess.run(
        [sys.executable, str(runner_path), "--simulate-failures"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    assert result_fail.returncode == 1
    assert "Regression gate validation: FAILED" in result_fail.stdout
