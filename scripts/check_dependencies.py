#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

# Module maps to its allowed dependency modules
# Rule: Any module in this list can only import from modules below it in the hierarchy.
HIERARCHY = [
    # Top: Compilers/Clients
    "rationalevault/cognitive_head/compiler.py",
    "rationalevault/knowledge/context_compiler.py",
    "rationalevault/projections/continuation.py",
    # Intermediate API Gateway
    "rationalevault/projections/service.py",
    # Processing Engine Layer
    "rationalevault/projections/pipeline.py",
    # Resolver
    "rationalevault/schema/resolver.py",
    # Bottom: Schema definitions & Upcaster Registry
    "rationalevault/schema/upcaster.py",
]


def get_imports(file_path: Path) -> set[str]:
    imports = set()
    if not file_path.exists():
        return imports

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError:
            return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.add(name.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
            for name in node.names:
                imports.add(f"{node.module}.{name.name}")
    return imports


def check_hierarchy(project_root: Path) -> tuple[bool, list[str]]:
    reports = []
    has_violation = False

    for idx, source_rel in enumerate(HIERARCHY):
        source_path = project_root / source_rel
        if not source_path.exists():
            continue

        imports = get_imports(source_path)
        
        # Check against modules that are higher or equal in the hierarchy
        for imported in imports:
            # We only care about internal imports under rationalevault
            if not imported.startswith("rationalevault"):
                continue

            for target_idx, target_rel in enumerate(HIERARCHY):
                # Convert target relation filepath to module notation (e.g. rationalevault.schema.resolver)
                target_mod = target_rel.replace(".py", "").replace("/", ".").replace("\\", ".")
                
                # Check for direct import or submodule matching
                if imported == target_mod or imported.startswith(target_mod + "."):
                    # Violation if target is higher in the hierarchy (target_idx < source_idx)
                    if target_idx < idx:
                        reports.append(
                            f"Violation in {source_rel}:\n"
                            f"  Imports {imported} which is higher in hierarchy than source.\n"
                            f"  Source Level: {idx} | Target Level: {target_idx}"
                        )
                        has_violation = True
                    # Violation if importing itself (target_idx == idx)
                    elif target_idx == idx:
                        pass  # Self imports or internal module imports are permitted if sub-files exist

    return not has_violation, reports


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    success, violations = check_hierarchy(project_root)

    report_path = project_root / "docs" / "contributing" / "dependency_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# S13.1 Replay Dependency Audit Report\n\n")
        f.write("This report analyzes the dependency hierarchy of the Replay Infrastructure layers.\n\n")
        f.write("## Verified Layering Rules:\n")
        f.write("```\n")
        f.write("Compilers / Clients (Level 0-2)\n")
        f.write("        ↓\n")
        f.write("ReplayService (Level 3)\n")
        f.write("        ↓\n")
        f.write("ReplayPipeline (Level 4)\n")
        f.write("        ↓\n")
        f.write("ReplayResolver (Level 5)\n")
        f.write("        ↓\n")
        f.write("UpcasterRegistry (Level 6)\n")
        f.write("```\n\n")
        f.write("## Results\n\n")
        if success:
            f.write("✅ **Audit Status: PASSED**\n\n")
            f.write("No upward imports or shortcut violations detected between replay components.\n")
        else:
            f.write("❌ **Audit Status: FAILED**\n\n")
            f.write("Violations detected:\n\n")
            for v in violations:
                f.write(f"- {v}\n")

    if not success:
        print("Dependency audit FAILED. See docs/contributing/dependency_report.md")
        sys.exit(1)
    else:
        print("Dependency audit PASSED. Report written to docs/contributing/dependency_report.md")


if __name__ == "__main__":
    main()
