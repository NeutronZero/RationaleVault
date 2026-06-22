from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from rationalevault.evaluation.run_handoff_suite import get_memory_mb, classify_complexity_curve, run_benchmark_simulation
from rationalevault.evaluation.benchmark_schema import HandoffBenchmark


def test_memory_measurement() -> None:
    mem = get_memory_mb()
    assert isinstance(mem, float)
    assert mem >= 0.0


def test_classify_complexity_curve() -> None:
    # Linear scale results mock
    linear_results = [
        {"benchmark_id": "f1a_scale_100", "events": {"generated": 100}, "performance": {"compile_time_ms": 1.0}},
        {"benchmark_id": "f1a_scale_1000", "events": {"generated": 1000}, "performance": {"compile_time_ms": 10.0}},
        {"benchmark_id": "f1a_scale_10000", "events": {"generated": 10000}, "performance": {"compile_time_ms": 100.0}},
    ]
    assert classify_complexity_curve(linear_results) == "LINEAR"

    # Degenerating scale results mock (superlinear growth)
    degenerating_results = [
        {"benchmark_id": "f1a_scale_100", "events": {"generated": 100}, "performance": {"compile_time_ms": 1.0}},
        {"benchmark_id": "f1a_scale_1000", "events": {"generated": 1000}, "performance": {"compile_time_ms": 10.0}},
        {"benchmark_id": "f1a_scale_10000", "events": {"generated": 10000}, "performance": {"compile_time_ms": 800.0}},
    ]
    assert classify_complexity_curve(degenerating_results) == "DEGENERATING"


def test_run_handoff_suite_stress_execution() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    runner_path = project_root / "rationalevault" / "evaluation" / "run_handoff_suite.py"

    # Running suite normally should pass validation
    res = subprocess.run(
        [sys.executable, str(runner_path)],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    assert res.returncode == 0
    assert "Regression gate validation: PASSED" in res.stdout
    assert "Replay Complexity Curve:" in res.stdout
    assert "SnapshotStore NOT justified yet" in res.stdout
