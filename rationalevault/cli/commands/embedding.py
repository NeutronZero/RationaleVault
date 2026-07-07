import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    parser_embedding = subparsers.add_parser("embedding", help="Embedding search over knowledge")
    embedding_subparsers = parser_embedding.add_subparsers(dest="embedding_command", required=True)
    
    parser_embedding_search = embedding_subparsers.add_parser("search", help="Semantic search over knowledge embeddings")
    parser_embedding_search.add_argument("--query", required=True, help="Query string")
    parser_embedding_search.add_argument("--k", type=int, default=5, help="Number of results (default: 5)")
    
    parser_embedding.set_defaults(func=handler)


def handler(args: argparse.Namespace) -> None:
    from rationalevault.embedding.cli import cmd_embedding
    cmd_embedding(args)
