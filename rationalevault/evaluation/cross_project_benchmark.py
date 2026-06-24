"""Cross-Project Benchmark Corpus — Test scenarios for CrossProjectProjection.

Defines deterministic test scenarios that validate cross-project knowledge
transfer before the evaluator runs. Follows the I8/I9 pattern of
benchmark → projection → evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from rationalevault.knowledge.models import (
    KnowledgeConfidence,
    KnowledgeDomain,
    KnowledgeLifecycle,
    KnowledgeObject,
    KnowledgeTransferability,
    KnowledgeType,
    ProvenanceChain,
)


def _conf() -> KnowledgeConfidence:
    return KnowledgeConfidence(
        memory_count=3, source_event_count=2, contradiction_count=0,
        average_memory_confidence=0.9, score=0.9,
    )


def _prov(kid: str) -> ProvenanceChain:
    return ProvenanceChain(
        knowledge_id=kid, source_memory_ids=["m1"],
        source_event_ids=["100"], synthesis_event_id="syn-1",
        confidence=_conf(), evidence_count=1,
    )


def _k(
    kid: str,
    title: str,
    project_id: str = "",
    transferability: str = KnowledgeTransferability.LOCAL_ONLY.value,
    ktype: KnowledgeType = KnowledgeType.ARCHITECTURE_PRINCIPLE,
) -> KnowledgeObject:
    return KnowledgeObject(
        id=kid, version=1, title=title, content=f"content for {title}",
        knowledge_type=ktype, knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=_conf(), importance="high", provenance=_prov(kid),
        supporting_memory_ids=[f"m-{kid}"],
        lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
        project_id=project_id,
        transferability=transferability,
    )


@dataclass
class BenchmarkScenario:
    """A single cross-project transfer scenario."""
    name: str
    description: str
    projects: dict[str, list[KnowledgeObject]]
    query: str
    expected_transferred_titles: list[str]
    expected_excluded_titles: list[str]
    transferability_filter: Optional[list[str]] = None


@dataclass
class BenchmarkCorpus:
    """Collection of benchmark scenarios for cross-project evaluation."""
    scenarios: list[BenchmarkScenario] = field(default_factory=list)

    def add_scenario(self, scenario: BenchmarkScenario) -> None:
        self.scenarios.append(scenario)

    def get_scenario(self, name: str) -> Optional[BenchmarkScenario]:
        for s in self.scenarios:
            if s.name == name:
                return s
        return None


def build_benchmark_corpus() -> BenchmarkCorpus:
    """Build the standard cross-project benchmark corpus."""
    corpus = BenchmarkCorpus()

    # Scenario 1: Basic transfer
    corpus.add_scenario(BenchmarkScenario(
        name="single_transfer",
        description="REUSABLE knowledge transfers, LOCAL_ONLY is excluded",
        projects={
            "proj_a": [
                _k("a1", "Use PostgreSQL for storage", "proj_a",
                   KnowledgeTransferability.REUSABLE.value),
                _k("a2", "Internal bug fix #123", "proj_a",
                   KnowledgeTransferability.LOCAL_ONLY.value),
            ],
            "proj_b": [
                _k("b1", "Use SQLite for dev", "proj_b",
                   KnowledgeTransferability.REUSABLE.value),
            ],
        },
        query="database",
        expected_transferred_titles=["Use PostgreSQL for storage", "Use SQLite for dev"],
        expected_excluded_titles=["Internal bug fix #123"],
    ))

    # Scenario 2: Organizational knowledge
    corpus.add_scenario(BenchmarkScenario(
        name="organizational_knowledge",
        description="ORGANIZATIONAL knowledge always transfers",
        projects={
            "proj_a": [
                _k("a1", "All projections must be deterministic", "proj_a",
                   KnowledgeTransferability.ORGANIZATIONAL.value),
            ],
            "proj_b": [],
        },
        query="determinism",
        expected_transferred_titles=["All projections must be deterministic"],
        expected_excluded_titles=[],
    ))

    # Scenario 3: Provenance preservation
    corpus.add_scenario(BenchmarkScenario(
        name="provenance_preservation",
        description="Transferred knowledge retains source project ID",
        projects={
            "proj_a": [
                _k("a1", "Use event sourcing", "proj_a",
                   KnowledgeTransferability.REUSABLE.value),
            ],
        },
        query="architecture",
        expected_transferred_titles=["Use event sourcing"],
        expected_excluded_titles=[],
    ))

    # Scenario 4: Determinism
    corpus.add_scenario(BenchmarkScenario(
        name="determinism",
        description="Same input produces same output",
        projects={
            "proj_a": [
                _k("a1", "Use PostgreSQL", "proj_a",
                   KnowledgeTransferability.REUSABLE.value),
                _k("a2", "Use Redis for caching", "proj_a",
                   KnowledgeTransferability.REUSABLE.value),
            ],
            "proj_b": [
                _k("b1", "Use MongoDB", "proj_b",
                   KnowledgeTransferability.REUSABLE.value),
            ],
        },
        query="storage",
        expected_transferred_titles=["Use PostgreSQL", "Use Redis for caching", "Use MongoDB"],
        expected_excluded_titles=[],
    ))

    # Scenario 5: Transferability filter
    corpus.add_scenario(BenchmarkScenario(
        name="transferability_filter",
        description="Filtering by transferability level works",
        projects={
            "proj_a": [
                _k("a1", "Use PostgreSQL", "proj_a",
                   KnowledgeTransferability.REUSABLE.value),
                _k("a2", "All projects use CI/CD", "proj_a",
                   KnowledgeTransferability.ORGANIZATIONAL.value),
            ],
        },
        query="deployment",
        expected_transferred_titles=["All projects use CI/CD"],
        expected_excluded_titles=["Use PostgreSQL"],
        transferability_filter=["ORGANIZATIONAL"],
    ))

    # Scenario 6: Empty project
    corpus.add_scenario(BenchmarkScenario(
        name="empty_project",
        description="Empty source project produces no transfer",
        projects={
            "proj_a": [],
            "proj_b": [
                _k("b1", "Use PostgreSQL", "proj_b",
                   KnowledgeTransferability.REUSABLE.value),
            ],
        },
        query="database",
        expected_transferred_titles=["Use PostgreSQL"],
        expected_excluded_titles=[],
    ))

    # Scenario 7: No matching knowledge — query has low relevance but knowledge still transfers
    corpus.add_scenario(BenchmarkScenario(
        name="no_match",
        description="Unrelated query yields low relevance but knowledge still transfers",
        projects={
            "proj_a": [
                _k("a1", "Use PostgreSQL", "proj_a",
                   KnowledgeTransferability.REUSABLE.value),
            ],
        },
        query="machine learning",
        expected_transferred_titles=["Use PostgreSQL"],
        expected_excluded_titles=[],
    ))

    return corpus
