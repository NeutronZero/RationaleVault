import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    parser_timeline = subparsers.add_parser("timeline", help="Chronological narrative of system evolution")
    timeline_subparsers = parser_timeline.add_subparsers(dest="timeline_command", required=True)
    
    parser_timeline_show = timeline_subparsers.add_parser("show", help="Show timeline entries")
    parser_timeline_show.add_argument("--limit", type=int, default=50, help="Max entries to show (default: 50)")
    parser_timeline_show.add_argument("--category", choices=["decision", "knowledge", "task", "question", "memory", "milestone", "system"], help="Filter by category")
    parser_timeline_show.add_argument("--format", choices=["table", "json"], default="table", help="Output format (default: table)")
    
    parser_timeline.set_defaults(func=handler)


def handler(args: argparse.Namespace) -> None:
    from rationalevault.timeline.cli import cmd_timeline
    cmd_timeline(args)
