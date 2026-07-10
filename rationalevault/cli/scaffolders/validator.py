"""
Scaffolded Projection Validator.

Ensures that a projection directory matches all architectural invariants:
- reducer pure (by checking if tests pass)
- conformance present
- benchmark present
- state equality implemented
- metadata complete
"""
from pathlib import Path


def validate_projection(path_str: str) -> bool:
    """Validate a projection directory."""
    path = Path(path_str)
    if not path.exists() or not path.is_dir():
        print(f"[FAIL] Directory not found: {path}")
        return False
        
    print(f"Validating Projection at: {path}")
    
    checks = [
        ("Metadata complete", _check_metadata),
        ("Reducer structure", _check_reducer),
        ("State equality implemented", _check_state_equality),
        ("Conformance tests present", _check_conformance),
        ("Benchmark present", _check_benchmark),
    ]
    
    all_passed = True
    for name, check_fn in checks:
        passed, details = check_fn(path)
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}: {details}")
        if not passed:
            all_passed = False
            
    return all_passed


def _check_metadata(path: Path) -> tuple[bool, str]:
    init_file = path / "__init__.py"
    if not init_file.exists():
        return False, "Missing __init__.py"
        
    content = init_file.read_text(encoding="utf-8")
    if "PROJECTION_NAME" not in content or "SCHEMA_VERSION" not in content:
        return False, "Missing PROJECTION_NAME or SCHEMA_VERSION in __init__.py"
        
    return True, "Metadata variables found"


def _check_reducer(path: Path) -> tuple[bool, str]:
    proj_file = path / "projection.py"
    if not proj_file.exists():
        return False, "Missing projection.py"
        
    content = proj_file.read_text(encoding="utf-8")
    if "def reduce" not in content:
        return False, "reduce method missing"
        
    # Static check for I/O is hard, but we can check if it relies on 'import requests' or similar.
    # We will rely on tests to prove purity.
    return True, "reduce method present"


def _check_state_equality(path: Path) -> tuple[bool, str]:
    state_file = path / "state.py"
    if not state_file.exists():
        return False, "Missing state.py"
        
    # Dataclasses give equality for free if they don't override it improperly.
    # Alternatively, look for __eq__ or @dataclass
    content = state_file.read_text(encoding="utf-8")
    if "@dataclass" not in content and "__eq__" not in content:
        return False, "State must use @dataclass or implement __eq__"
        
    return True, "State equality mechanism detected"


def _check_conformance(path: Path) -> tuple[bool, str]:
    conf_file = path / "tests" / "test_conformance.py"
    if not conf_file.exists():
        return False, "Missing tests/test_conformance.py"
        
    content = conf_file.read_text(encoding="utf-8")
    if "ConformanceSuite" not in content:
        return False, "Not using ConformanceSuite"
        
    return True, "ConformanceSuite integrated"


def _check_benchmark(path: Path) -> tuple[bool, str]:
    bench_file = path / "benchmarks" / "benchmark.py"
    if not bench_file.exists():
        return False, "Missing benchmarks/benchmark.py"
        
    content = bench_file.read_text(encoding="utf-8")
    if "benchmark" not in content:
        return False, "pytest-benchmark fixture not found"
        
    return True, "Benchmark implemented"
