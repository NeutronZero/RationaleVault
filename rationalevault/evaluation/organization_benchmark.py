"""Organization Benchmark Corpus — Test scenarios for OrganizationProjection."""
from __future__ import annotations

from dataclasses import dataclass, field

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
    kid: str, title: str, project_id: str = "",
    transferability: str = KnowledgeTransferability.REUSABLE.value,
    ktype: KnowledgeType = KnowledgeType.ARCHITECTURE_PRINCIPLE,
    content: str | None = None,
) -> KnowledgeObject:
    return KnowledgeObject(
        id=kid, version=1, title=title,
        content=content or f"content for {title}",
        knowledge_type=ktype, knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=_conf(), importance="high", provenance=_prov(kid),
        supporting_memory_ids=[f"m-{kid}"],
        lifecycle_status=KnowledgeLifecycle.ACTIVE.value,
        project_id=project_id,
        transferability=transferability,
    )


@dataclass
class OrganizationBenchmarkScenario:
    name: str
    description: str
    knowledge_by_project: dict[str, list[KnowledgeObject]]
    expected_lineage_count_min: int = 0
    expected_shared_count_min: int = 0
    expected_conflict_count_min: int = 0
    expected_invariant_count_min: int = 0


@dataclass
class OrganizationBenchmarkCorpus:
    scenarios: list[OrganizationBenchmarkScenario] = field(default_factory=list)

    def add_scenario(self, scenario: OrganizationBenchmarkScenario) -> None:
        self.scenarios.append(scenario)

    def get_scenario(self, name: str) -> OrganizationBenchmarkScenario | None:
        for s in self.scenarios:
            if s.name == name:
                return s
        return None


def build_organization_benchmark() -> OrganizationBenchmarkCorpus:
    """Build the standard organization benchmark corpus."""
    corpus = OrganizationBenchmarkCorpus()

    # Scenario 1: Single project, no transfer
    corpus.add_scenario(OrganizationBenchmarkScenario(
        name="single_project",
        description="One project, no cross-project transfer",
        knowledge_by_project={
            "proj_a": [
                _k("a1", "Use PostgreSQL", "proj_a"),
                _k("a2", "Auth via JWT", "proj_a"),
            ],
        },
        expected_lineage_count_min=0,
        expected_shared_count_min=0,
    ))

    # Scenario 2: Linear transfer A → B → C
    corpus.add_scenario(OrganizationBenchmarkScenario(
        name="linear_transfer",
        description="Knowledge transferred A → B → C",
        knowledge_by_project={
            "proj_a": [
                _k("a1", "Use PostgreSQL", "proj_a"),
            ],
            "proj_b": [
                _k("b1", "Use PostgreSQL", "proj_a", content="content for Use PostgreSQL"),
            ],
            "proj_c": [
                _k("c1", "Use PostgreSQL", "proj_a", content="content for Use PostgreSQL"),
            ],
        },
        expected_lineage_count_min=1,
        expected_shared_count_min=1,
    ))

    # Scenario 3: Branching transfer A → B, A → C
    corpus.add_scenario(OrganizationBenchmarkScenario(
        name="branching_transfer",
        description="Knowledge transferred A → B and A → C",
        knowledge_by_project={
            "proj_a": [
                _k("a1", "Use PostgreSQL", "proj_a"),
            ],
            "proj_b": [
                _k("b1", "Use PostgreSQL", "proj_a", content="content for Use PostgreSQL"),
            ],
            "proj_c": [
                _k("c1", "Use PostgreSQL", "proj_a", content="content for Use PostgreSQL"),
            ],
        },
        expected_lineage_count_min=1,
        expected_shared_count_min=1,
    ))

    # Scenario 4: Cross-project contradiction
    corpus.add_scenario(OrganizationBenchmarkScenario(
        name="cross_project_contradiction",
        description="Same title + type, different content across projects",
        knowledge_by_project={
            "proj_a": [
                _k("a1", "Auth System", "proj_a",
                   content="content for Auth System using JWT tokens"),
            ],
            "proj_b": [
                _k("b1", "Auth System", "proj_b",
                   content="content for Auth System using OAuth2 flow"),
            ],
        },
        expected_conflict_count_min=1,
    ))

    # Scenario 5: Invariant spanning projects
    corpus.add_scenario(OrganizationBenchmarkScenario(
        name="invariant_spanning",
        description="PROJECT_INVARIANT present in 2+ projects",
        knowledge_by_project={
            "proj_a": [
                _k("a1", "No LLM in prod", "proj_a", ktype=KnowledgeType.PROJECT_INVARIANT),
            ],
            "proj_b": [
                _k("b1", "No LLM in prod", "proj_b", ktype=KnowledgeType.PROJECT_INVARIANT),
            ],
        },
        expected_invariant_count_min=1,
    ))

    # Scenario 6: Determinism
    corpus.add_scenario(OrganizationBenchmarkScenario(
        name="determinism",
        description="Same inputs produce identical OrganizationState",
        knowledge_by_project={
            "proj_a": [_k("a1", "Use PG", "proj_a")],
            "proj_b": [_k("b1", "Use PG", "proj_a", content="content for Use PG")],
        },
        expected_lineage_count_min=1,
    ))

    # Scenario 7: Telemetry distribution
    corpus.add_scenario(OrganizationBenchmarkScenario(
        name="telemetry_distribution",
        description="Mixed LOCAL_ONLY/REUSABLE/ORGANIZATIONAL distribution",
        knowledge_by_project={
            "proj_a": [
                _k("a1", "Internal fix", "proj_a",
                   transferability=KnowledgeTransferability.LOCAL_ONLY.value),
                _k("a2", "Use PG", "proj_a",
                   transferability=KnowledgeTransferability.REUSABLE.value),
                _k("a3", "CI/CD policy", "proj_a",
                   transferability=KnowledgeTransferability.ORGANIZATIONAL.value),
            ],
        },
    ))

    return corpus
