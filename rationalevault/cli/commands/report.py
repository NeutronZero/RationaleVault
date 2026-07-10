import argparse
import json
from pathlib import Path

def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("report", help="Generate API compatibility report from snapshot")
    parser.add_argument("--output", "-o", default="API_REPORT.md", help="Output Markdown file path")
    parser.set_defaults(func=handler)

def handler(args: argparse.Namespace) -> None:
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    snapshot_path = project_root / "tests" / "fixtures" / "public_api_snapshot.json"
    
    if not snapshot_path.exists():
        print(f"Error: Snapshot not found at {snapshot_path}")
        return
        
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
        
    tiers = {
        "stable": [],
        "advanced": [],
        "internal": []
    }
    
    for module_name, symbols in snapshot.items():
        for sym_name, meta in symbols.items():
            tier = meta.get("tier", "internal")
            if tier not in tiers:
                tiers[tier] = []
            tiers[tier].append((sym_name, module_name, meta))
            
    # Sort symbols by module then name
    for t in tiers.values():
        t.sort(key=lambda x: (x[1], x[0]))
        
    report = ["# RationaleVault API Compatibility Report\n"]
    
    for tier in ["stable", "advanced", "internal"]:
        if not tiers.get(tier):
            continue
            
        report.append(f"## {tier.capitalize()} APIs\n")
        
        if tier == "stable":
            report.append("> **Compatibility:** Major-only changes. Guaranteed stable.\n")
        elif tier == "advanced":
            report.append("> **Compatibility:** Requires deprecation period. May change in minor releases.\n")
        else:
            report.append("> **Compatibility:** No guarantees.\n")
            
        report.append("| Symbol | Module | Kind | Introduced | Deprecated | Replacement |")
        report.append("|--------|--------|------|------------|------------|-------------|")
        
        for sym_name, mod_name, meta in tiers[tier]:
            kind = meta.get("kind", "unknown")
            intro = meta.get("introduced", "-")
            depr = meta.get("deprecated") or "-"
            repl = meta.get("replacement") or "-"
            
            report.append(f"| `{sym_name}` | `{mod_name}` | {kind} | {intro} | {depr} | {repl} |")
            
        report.append("")
        
    out_path = Path(args.output)
    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"[SUCCESS] API Report generated at {out_path.absolute()}")
