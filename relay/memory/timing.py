from __future__ import annotations

from dataclasses import dataclass

@dataclass
class RetrievalTiming:
    query_analysis_ms: float
    planning_ms: float
    search_ms: float
    ranking_ms: float
    citation_ms: float
    total_ms: float

    def to_dict(self) -> dict[str, float]:
        return {
            "query_analysis_ms": self.query_analysis_ms,
            "planning_ms": self.planning_ms,
            "search_ms": self.search_ms,
            "ranking_ms": self.ranking_ms,
            "citation_ms": self.citation_ms,
            "total_ms": self.total_ms,
        }
