"""Unit tests for RationaleVault Release Hardening & Diagnostics (Sprint I8)."""
from __future__ import annotations

import json
from pathlib import Path

from rationalevault.diagnostics.doctor import run_diagnostics
from rationalevault.evaluation.evaluator import run_full_evaluation
from rationalevault.evaluation.validate_install import validate_all_imports


def test_diagnostics_doctor() -> None:
    # 1. Run doctor checks
    report = run_diagnostics()

    # 2. Check structure
    assert report.rationalevault_version == "1.0.1"
    assert len(report.checks) > 0
    assert report.overall_passed is True

    # Validate that active Projection Chain check is present and passing
    chain_check = next((c for c in report.checks if c.component == "Projection Chain"), None)
    assert chain_check is not None
    assert chain_check.status == "PASS"


def test_unified_evaluator_and_manifest() -> None:
    # 1. Execute unified evaluation
    result = run_full_evaluation()

    # 2. Verify result fields
    assert result.rationalevault_version == "1.0.1"
    assert result.schema_version == "1.0"
    assert result.overall_passed is True

    # 3. Verify manifest existence and structure
    manifest_path = Path(result.report_path)
    assert manifest_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["rationalevault_version"] == "1.0.1"
    assert manifest["schema_version"] == "1.0"
    assert "evaluations" in manifest
    assert "examples" in manifest
    assert "metrics" in manifest

    # Example projects must pass verification
    assert manifest["examples"]["basic_memory"] == "PASS"
    assert manifest["examples"]["knowledge_synthesis"] == "PASS"
    assert manifest["examples"]["multi_agent_handoff"] == "PASS"


def test_installation_validation() -> None:
    # Verify that validate_all_imports executes successfully
    passed = validate_all_imports()
    assert passed is True
