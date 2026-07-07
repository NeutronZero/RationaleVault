import argparse
from rationalevault.cli.commands import doctor, init, timeline, governance, recommendation, embedding, memory, knowledge, others

COMMANDS = [
    init,
    doctor,
    timeline,
    governance,
    recommendation,
    embedding,
    memory,
    knowledge,
    others,
]

def register_all(subparsers: argparse._SubParsersAction) -> None:
    for cmd in COMMANDS:
        cmd.register(subparsers)
