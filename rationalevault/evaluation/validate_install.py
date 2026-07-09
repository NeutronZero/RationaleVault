"""RationaleVault Installation Validation — Runs sanity import checks to verify the package is installed correctly."""
from __future__ import annotations
from rationalevault.logging import get_logger

logger = get_logger(__name__)



import sys


def validate_all_imports() -> bool:
    print("=== RationaleVault Installation Validation ===")
    
    stages = [
        ("Core DB & Store", "rationalevault.db.sqlite_store", ["SQLiteEventStore"]),
        ("Memory Engine", "rationalevault.memory.sqlite_provider", ["SQLiteMemoryProvider"]),
        ("Knowledge Engine", "rationalevault.knowledge.store", ["SQLiteKnowledgeProvider"]),
        ("Graph Engine", "rationalevault.knowledge.graph", ["GraphProjection", "KnowledgeNode"]),
        ("Compiler Adapters", "rationalevault.compilers.registry", ["get_context_compiler"]),
        ("Diagnostics Engine", "rationalevault.diagnostics.doctor", ["run_diagnostics", "HealthCheck"]),
        ("Unified Evaluator", "rationalevault.evaluation.evaluator", ["run_full_evaluation", "EvaluationResult"]),
    ]

    all_passed = True
    for name, module_path, symbols in stages:
        try:
            mod = __import__(module_path, fromlist=symbols)
            for s in symbols:
                assert hasattr(mod, s), f"Symbol '{s}' is missing in {module_path}"
            print(f"  [PASS] {name:<20} : Imports successfully")
        except Exception as e:
            print(f"  [FAIL] {name:<20} : {str(e)}")
            all_passed = False

    return all_passed


def main() -> None:
    passed = validate_all_imports()
    if passed:
        print("\n[SUCCESS] RationaleVault installation verified successfully!")
        sys.exit(0)
    else:
        print("\n[ERROR] Installation check failed. Check diagnostic messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
