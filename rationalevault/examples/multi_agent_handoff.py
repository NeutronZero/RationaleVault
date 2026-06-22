"""RationaleVault built-in example: Multi-Agent Handoff (Context -> Compiler -> Adapter).

Bundled inside the rationalevault package for CWD-independent execution.
"""
from __future__ import annotations

from rationalevault.knowledge.context_compiler import ContextPackage
from rationalevault.knowledge.context_types import ContextCitation
from rationalevault.memory.models import MemoryRecord, MemoryType
from rationalevault.compilers.registry import get_context_compiler


def main() -> None:
    print("--- Running RationaleVault Example: Multi-Agent Handoff ---")

    # 1. Setup mock memory citation
    citation = ContextCitation(
        source_type="memory",
        source_id="mem_handoff_1",
        title="Agent A Status Reflection",
        content="Handoff checklist complete. All unit tests are passing and graph projection is online.",
        relevance_score=0.9,
        confidence=1.0,
        reasons=["manual"],
        source_event_ids=["ev_handoff"],
    )

    # 2. Package context
    print("Building ContextPackage for Agent B...")
    package = ContextPackage(
        context_id="ctx_handoff_abc",
        query="handoff summary",
        profile="default",
        created_at="2026-06-22T00:00:00",
        citations=[citation],
        inclusion_reasons=["latest status reflection"],
        source_counts={"memory": 1},
    )

    # 3. Compile for Claude adapter
    print("Compiling for Claude adapter...")
    compiler = get_context_compiler("claude")
    output = compiler.compile(package)

    # 4. Show rendered block
    print("\nRendered Context Package:")
    print("=" * 60)
    to_print = output.rendered_content[:300] + "...\n[TRUNCATED FOR DEMO]"
    try:
        print(to_print)
    except UnicodeEncodeError:
        print(to_print.encode("ascii", errors="replace").decode("ascii"))
    print("=" * 60)

    print("Example executed successfully!\n")


if __name__ == "__main__":
    main()
