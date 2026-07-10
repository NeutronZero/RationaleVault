import argparse
import sys
from pathlib import Path

from rationalevault.cli.scaffolders.projection import scaffold_projection
from rationalevault.cli.scaffolders.skill import scaffold_skill


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("new", help="Scaffold new components (projection, skill, etc.)")
    new_subparsers = parser.add_subparsers(dest="type", required=True)

    # new projection
    proj_parser = new_subparsers.add_parser("projection", help="Scaffold a new projection")
    proj_parser.add_argument("name", help="Name of the projection (e.g. task_tracker)")
    proj_parser.add_argument("--with-cli", action="store_true", help="Generate CLI adapter stub")
    proj_parser.add_argument("--with-mcp", action="store_true", help="Generate MCP tool stub")
    proj_parser.add_argument("--with-runtime", action="store_true", help="Generate runtime stub")
    
    # new skill
    skill_parser = new_subparsers.add_parser("skill", help="Scaffold a new skill")
    skill_parser.add_argument("name", help="Name of the skill (e.g. write_file)")

    parser.set_defaults(func=handler)


def handler(args: argparse.Namespace) -> None:
    dest_dir = Path.cwd() / args.name
    
    if dest_dir.exists():
        print(f"Error: Directory '{args.name}' already exists.")
        sys.exit(1)

    if args.type == "projection":
        scaffold_projection(
            name=args.name, 
            dest=dest_dir,
            with_cli=args.with_cli,
            with_mcp=args.with_mcp,
            with_runtime=args.with_runtime
        )
        print(f"[SUCCESS] Scaffolded new projection in ./{args.name}")
        print("Running post-generation validation...")
        
        # Run projection structural validation
        from rationalevault.cli.scaffolders.validator import validate_projection
        if not validate_projection(str(dest_dir)):
            print("[WARNING] Structural validation failed.")
            
        # Run pytest
        import subprocess
        print(f"Running unit tests for ./{args.name}...")
        result = subprocess.run(["pytest", str(dest_dir)], capture_output=True, text=True)
        if result.returncode == 0:
            print("[PASS] Generated project passed all tests.")
        else:
            print("[WARNING] Generated project failed unit tests!")
            print(result.stdout)
        
    elif args.type == "skill":
        scaffold_skill(name=args.name, dest=dest_dir)
        print(f"[SUCCESS] Scaffolded new skill in ./{args.name}")
        print(f"Run tests: pytest ./{args.name}/tests/")
