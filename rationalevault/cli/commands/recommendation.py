import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    parser_recommendation = subparsers.add_parser("recommendation", help="Derived recommendations from event history")
    recommendation_subparsers = parser_recommendation.add_subparsers(dest="recommendation_command", required=True)
    
    parser_recommendation_show = recommendation_subparsers.add_parser("show", help="Show recommendations")
    parser_recommendation_show.add_argument("--limit", type=int, default=10, help="Max recommendations to show (default: 10)")
    parser_recommendation_show.add_argument("--for", dest="for_entity", help="Filter by target entity (task_id, knowledge_id, etc.)")
    parser_recommendation_show.add_argument("--category", choices=["next_action", "knowledge_gap", "risk", "optimization", "follow_up"], help="Filter by category")
    parser_recommendation_show.add_argument("--format", choices=["table", "json"], default="table", help="Output format (default: table)")
    
    parser_recommendation.set_defaults(func=handler)


def handler(args: argparse.Namespace) -> None:
    from rationalevault.recommendation.cli import cmd_recommendation
    # Handle the rename of --for to for_entity to avoid python keyword clash
    if hasattr(args, 'for_entity'):
        setattr(args, 'for', args.for_entity)
    cmd_recommendation(args)
