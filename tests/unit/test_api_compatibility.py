"""
API Compatibility Tests.

Ensures that the public API (Stable and Advanced tiers) does not silently
lose symbols or break compatibility without a formal update to the snapshot.
"""
from __future__ import annotations

import json
from pathlib import Path
import importlib
import inspect

import pytest

def get_symbol_kind(symbol):
    if inspect.isclass(symbol):
        return "class"
    if inspect.isroutine(symbol):
        return "function"
    if inspect.ismodule(symbol):
        return "module"
    if isinstance(symbol, type):
        return "class"
    return type(symbol).__name__


def test_public_api_compatibility():
    """
    Compare the current __all__ lists of major packages against the recorded snapshot.
    If symbols are missing, this is a BREAKING CHANGE and should fail CI.
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    snapshot_path = project_root / "tests" / "fixtures" / "public_api_snapshot.json"
    
    assert snapshot_path.exists(), "Missing public API snapshot"
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
        
    violations = []
    
    for module_name, expected_symbols in snapshot.items():
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            violations.append(f"Public module {module_name} could not be imported.")
            continue
            
        if not hasattr(module, "__all__"):
            violations.append(f"Public module {module_name} is missing __all__ declaration.")
            continue
            
        actual_symbols = set(module.__all__)
        expected_set = set(expected_symbols.keys())
        
        # Check for missing symbols (BREAKING CHANGE)
        missing = expected_set - actual_symbols
        if missing:
            violations.append(f"BREAKING CHANGE: {module_name} is missing exported symbols: {missing}")
            
        # Check symbol kinds (BREAKING CHANGE if changed)
        for sym_name in expected_set.intersection(actual_symbols):
            sym = getattr(module, sym_name)
            actual_kind = get_symbol_kind(sym)
            expected_kind = expected_symbols[sym_name]["kind"]
            
            if actual_kind != expected_kind:
                violations.append(
                    f"BREAKING CHANGE: {module_name}.{sym_name} changed kind from {expected_kind} to {actual_kind}"
                )
            
        # Optional: Warn on new symbols not in snapshot (so developers remember to update it)
        # But failing on new symbols might be too aggressive. We will strictly fail on missing.
        
    assert not violations, "API Compatibility Violations:\n" + "\n".join(violations)
