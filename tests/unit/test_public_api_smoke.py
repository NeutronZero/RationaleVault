"""
Public API Smoke Test.

Verifies that every symbol listed in the public_api_snapshot.json can be successfully
imported from its root module without raising an AttributeError or ImportError.
"""
import json
from pathlib import Path
import importlib

def test_public_api_smoke():
    project_root = Path(__file__).resolve().parent.parent.parent
    snapshot_path = project_root / "tests" / "fixtures" / "public_api_snapshot.json"
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
        
    for module_name, symbols in snapshot.items():
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            assert False, f"Smoke test failed: could not import module {module_name}. Error: {e}"
            
        for sym_name in symbols.keys():
            try:
                getattr(module, sym_name)
            except AttributeError as e:
                assert False, f"Smoke test failed: symbol {sym_name} is missing from {module_name}. Error: {e}"
