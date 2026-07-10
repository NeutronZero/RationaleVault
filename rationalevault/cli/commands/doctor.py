import argparse
import sys


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("doctor", help="Check diagnostics and system status")
    
    doctor_subparsers = parser.add_subparsers(dest="doctor_target", required=False)
    proj_parser = doctor_subparsers.add_parser("projection", help="Validate a projection directory")
    proj_parser.add_argument("path", help="Path to the projection directory")
    
    parser.set_defaults(func=handler)


def handler(args: argparse.Namespace) -> None:
    if getattr(args, "doctor_target", None) == "projection":
        from rationalevault.cli.scaffolders.validator import validate_projection
        sys.exit(0 if validate_projection(args.path) else 1)

    from rationalevault.diagnostics.doctor import run_diagnostics
    report = run_diagnostics()
    
    print("\n=== RationaleVault Doctor ===")
    print(f"RationaleVault version: {report.rationalevault_version}")
    print(f"Generated at:  {report.generated_at}\n")
    for check in report.checks:
        status_symbol = f"[{check.status}]"
        print(f"  {check.component:<22} {status_symbol:<8} : {check.details}")
    print("-" * 65)
    print(f"Overall Result: {'PASS' if report.overall_passed else 'FAIL'}")
    if not report.overall_passed:
        sys.exit(1)
