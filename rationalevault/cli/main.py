import argparse
import sys
from rationalevault.cli.registry import register_all

def main() -> None:
    parser = argparse.ArgumentParser(description="RationaleVault Cognitive Continuity CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_all(subparsers)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
