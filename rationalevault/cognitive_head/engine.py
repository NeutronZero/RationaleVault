from __future__ import annotations

from typing import Optional
from rationalevault.projections.knowledge import KnowledgeState
from rationalevault.cognitive_head.config import ReasoningConfig
from rationalevault.cognitive_head.evidence import EvidenceAggregator
from rationalevault.cognitive_head.assessment import AssessmentEngine
from rationalevault.cognitive_head.belief import BeliefEngine
from rationalevault.cognitive_head.propagation import PropagationEngine
from rationalevault.cognitive_head.reasoning_report import ReasoningReport, ReasoningReportBuilder
from rationalevault.cognitive_head.synthesis import SynthesisConfig, SynthesisEngine
from rationalevault.cognitive_head.decision import DecisionGatePolicy, DecisionGate, DecisionSet
from rationalevault.knowledge.contradiction import ContradictionEngine
from rationalevault.memory.models import MemoryRecord, MemoryType


class ReasoningEngine:
    """Orchestrates the cognitive reasoning pipeline to build a ReasoningReport."""

    @staticmethod
    def reason(
        knowledge_states: list[KnowledgeState],
        suppressed_ids: Optional[set[str]] = None,
        config: ReasoningConfig = ReasoningConfig()
    ) -> ReasoningReport:
        # 1. Aggregate knowledge states into evidence bundles
        bundles = EvidenceAggregator.aggregate(knowledge_states)

        # 2. Assess evidence and construct initial beliefs
        beliefs = []
        concept_id_to_belief_id = {}
        for b in bundles:
            assessment = AssessmentEngine.assess(b, config)
            belief = BeliefEngine.construct(b.title, b.content, assessment, b.supporting_evidence)
            beliefs.append(belief)
            concept_id_to_belief_id[b.concept_id] = belief.belief_id

        # 3. Build overall support graph across states to propagate confidence
        support_graph: dict[str, list[str]] = {}
        for state in knowledge_states:
            for src, targets in state.support_graph.items():
                support_graph.setdefault(src, []).extend(targets)

        # 4. Propagate confidence through the belief dependency DAG
        beliefs = PropagationEngine.propagate_beliefs(beliefs, concept_id_to_belief_id, support_graph, config)

        # 5. Detect contradictions at the aggregated knowledge level
        temp_records = []
        seen_ids = set()
        for state in sorted(knowledge_states, key=lambda s: s.project_id):
            for k in state.active_knowledge:
                if k.id not in seen_ids:
                    temp_records.append(MemoryRecord(
                        id=k.id,
                        version=k.version,
                        title=k.title,
                        content=k.content,
                        memory_type=MemoryType.DECISION,
                        importance="medium",
                        lifecycle_status="active",
                        source_event_ids=[],
                        source_type="manual"
                    ))
                    seen_ids.add(k.id)

        contradictions = ContradictionEngine.detect(temp_records, suppressed_ids)

        # 6. Build the final ReasoningReport with config
        return ReasoningReportBuilder.build(beliefs, contradictions, config)

    @staticmethod
    def synthesize(
        report: ReasoningReport,
        synthesis_config: SynthesisConfig = SynthesisConfig(),
        gate_policy: DecisionGatePolicy = DecisionGatePolicy(),
    ) -> DecisionSet:
        """
        Consume a ReasoningReport and produce a DecisionSet.

        This is an independent call path from reason().  The ReasoningReport
        is consumed read-only — it is never mutated.

        Steps:
          1. SynthesisEngine.synthesize() — Phase 1 + 2 (candidate generation
             and ranking) → SynthesisReport
          2. DecisionGate.gate()          — Phase 3 (policy evaluation) → DecisionSet
        """
        synthesis = SynthesisEngine.synthesize(report, synthesis_config)
        return DecisionGate.gate(synthesis, gate_policy)
