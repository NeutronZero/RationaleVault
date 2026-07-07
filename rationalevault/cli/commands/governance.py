import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    parser_governance = subparsers.add_parser("governance", help="Policy evaluation warnings and decisions")
    governance_subparsers = parser_governance.add_subparsers(dest="governance_command", required=True)
    
    parser_governance_show = governance_subparsers.add_parser("show", help="Show governance warnings")
    parser_governance_show.add_argument("--limit", type=int, default=50, help="Max warnings to show (default: 50)")
    parser_governance_show.add_argument("--severity", choices=["info", "warning", "critical"], help="Filter by severity")
    parser_governance_show.add_argument("--action", choices=["notify", "block", "suggest", "log"], help="Filter by action")
    parser_governance_show.add_argument("--format", choices=["table", "json"], default="table", help="Output format (default: table)")
    
    parser_governance.set_defaults(func=handler)


def handler(args: argparse.Namespace) -> None:
    from rationalevault.governance.cli import cmd_governance
    cmd_governance(args)
