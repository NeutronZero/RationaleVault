import argparse
import json
import subprocess
import sys
from pathlib import Path

THRESHOLDS = {
    "test_replay": 0.05,
    "test_snapshot": 0.05,
    "test_projection_replay": 0.05,
    "test_runtime": 0.10,
    "test_cli": None,       # informational
    "test_embedding": None  # informational
}

def get_threshold(test_name: str) -> float | None:
    for prefix, threshold in THRESHOLDS.items():
        if prefix in test_name:
            return threshold
    return 0.10 # default 10%

def run_benchmarks(output_file: Path) -> bool:
    print("Running pytest-benchmark...")
    # Run pytest and output benchmark to json. We don't fail if tests fail, we will process the json.
    cmd = ["pytest", "tests/performance/", "-n", "0", "--benchmark-only", f"--benchmark-json={output_file}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
    
    if not output_file.exists():
        print("Failed to generate benchmark JSON.")
        return False
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=str, required=True, help="Path to baseline JSON")
    parser.add_argument("--save-baseline", action="store_true", help="Save the current run as the new baseline")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    current_output = project_root / "current_benchmarks.json"
    
    if not run_benchmarks(current_output):
        sys.exit(1)
        
    with open(current_output, "r") as f:
        current_data = json.load(f)
        
    if args.save_baseline:
        baseline_path = Path(args.baseline)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(current_data, indent=4))
        print(f"Saved new baseline to {args.baseline}")
        sys.exit(0)
        
    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        print(f"Baseline file {args.baseline} not found!")
        sys.exit(1)
        
    with open(baseline_path, "r") as f:
        baseline_data = json.load(f)
        
    baseline_map = {b["name"]: b["stats"]["mean"] for b in baseline_data["benchmarks"]}
    
    failed = False
    
    print("\n--- Performance Report ---")
    for current in current_data["benchmarks"]:
        name = current["name"]
        curr_mean = current["stats"]["mean"]
        base_mean = baseline_map.get(name)
        
        if not base_mean:
            print(f"[-] {name}: No baseline (current: {curr_mean:.6f}s)")
            continue
            
        diff = (curr_mean - base_mean) / base_mean
        threshold = get_threshold(name)
        
        sign = "+" if diff > 0 else ""
        print(f"[*] {name}: {curr_mean:.6f}s (baseline: {base_mean:.6f}s) | diff: {sign}{diff*100:.2f}%")
        
        if threshold is not None and diff > threshold:
            print(f"    -> [ERROR] Regression exceeded {threshold*100}% threshold!")
            failed = True
            
    if failed:
        print("\n[FAIL] Performance regression detected.")
        sys.exit(1)
    else:
        print("\n[PASS] All performance checks passed.")

if __name__ == "__main__":
    main()
