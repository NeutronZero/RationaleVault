from __future__ import annotations

from rationalevault.memory.factory import get_memory_provider
from rationalevault.memory.models import MemoryRecord
from rationalevault.memory.retrieval import retrieve_ranked_memories
from rationalevault.memory.ranking import RetrievalScore


def compile_memory_context(query: str) -> dict[str, list[tuple[MemoryRecord, RetrievalScore]]]:
    """
    Compiles memory records matching a query into a structured context dictionary grouped by MemoryType.
    """
    scored_records = retrieve_ranked_memories(query, limit=100)

    context = {
        "DECISION": [],
        "DECISION_RATIONALE": [],
        "LESSON_LEARNED": [],
        "FAILURE": [],
        "ARCHITECTURE": [],
        "IMPLEMENTATION_NOTE": [],
        "RESEARCH": [],
        "WORKFLOW": [],
    }

    for r, score in scored_records:
        t = r.memory_type.value
        if t in context:
            context[t].append((r, score))

    return context
