from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvaluationThresholds:
    # Continuity thresholds
    MIN_GOAL_RECALL: float = 1.00
    MIN_DECISION_RECALL: float = 1.00
    MIN_QUESTION_RECALL: float = 1.00
    MIN_TASK_RECALL: float = 0.95
    MAX_DRIFT_RATE: float = 0.05
    MAX_DEGRADATION_RATE: float = 0.05

    # Memory thresholds
    MIN_MEMORY_PROVENANCE_PCT: float = 1.00
    MIN_MEMORY_DEDUPLICATION_RATE: float = 0.95

    # Knowledge Evaluation thresholds (Sprint I4.5)
    MIN_KNOWLEDGE_PRECISION: float = 0.80
    MIN_SEMANTIC_RECALL: float = 0.80
    MIN_IDENTITY_RECALL: float = 0.50
    MIN_KNOWLEDGE_F1: float = 0.80
    MIN_KNOWLEDGE_PROVENANCE_PCT: float = 1.00
    MIN_KNOWLEDGE_DETERMINISM: float = 1.00
    MIN_CONTRADICTION_PRECISION: float = 0.90
    MAX_FALSE_CONTRADICTIONS: int = 0

    # Context Evaluation thresholds (Sprint I5.5)
    MIN_CONTEXT_COMPLETENESS: float = 0.67
    MIN_SOURCE_BALANCE: float = 0.15
    MIN_CONTEXT_PRECISION: float = 0.70
    MIN_CONTEXT_RECALL: float = 0.50
    MIN_CONTEXT_F1: float = 0.60
    MAX_CONTEXT_REDUNDANCY: float = 0.25
    MIN_CONTEXT_DETERMINISM: float = 1.0
    MAX_CONTEXT_COMPILE_MS: float = 500.0

    # Compiler Evaluation thresholds (Sprint I6.5)
    MIN_COMPILER_CITATION_PRESERVATION: float = 0.80
    MIN_COMPILER_MEMORY_PRESERVATION: float = 0.80
    MIN_COMPILER_KNOWLEDGE_PRESERVATION: float = 0.80
    MIN_COMPILER_EVENT_PRESERVATION: float = 0.80
    MIN_COMPILER_SOURCE_EVENT_PRESERVATION: float = 0.80
    MAX_COMPILER_COMPILE_MS: float = 100.0
    MIN_COMPILER_DETERMINISM: float = 1.0

    # Continuity Validation thresholds (Sprint I7)
    MIN_CONTINUITY_GOAL_RECALL: float = 1.00
    MIN_CONTINUITY_DECISION_RECALL: float = 1.00
    MIN_CONTINUITY_RATIONALE_RECALL: float = 0.95
    MIN_CONTINUITY_TASK_RECALL: float = 0.95
    MIN_CONTINUITY_KNOWLEDGE_RECALL: float = 0.80
    MIN_CONTINUITY_QUESTION_RECALL: float = 1.00
    MIN_CONTINUITY_OVERALL: float = 0.90
    MIN_CONTEXT_GAIN: float = 0.10

    # Knowledge Projection thresholds (Sprint I8)
    MIN_KP_TRACEABILITY: float = 1.00
    MIN_KP_CONTRADICTION_DETECTION: float = 0.90
    MIN_KP_INVARIANT_PRESERVATION: float = 1.00
    MIN_KP_SUPERSESSION_COMPLETENESS: float = 0.95
    MIN_KP_EPISTEMIC_ACCURACY: float = 0.95
    MIN_KP_LIFECYCLE_FILTERING: float = 1.00
    MIN_KP_HEALTH_COMPUTATION: float = 1.00
    MIN_KP_OVERALL: float = 0.95

    # Graph Projection thresholds (Sprint I9.5)
    MIN_GP_CONNECTIVITY: float = 0.90
    MIN_GP_REFERENTIAL_INTEGRITY: float = 1.00
    MIN_GP_DETERMINISM: float = 1.00
    MIN_GP_ORPHAN_RATE: float = 0.20
    MIN_GP_ADJACENCY_CONSISTENCY: float = 1.00
    MIN_GP_PROVENANCE_COMPLETENESS: float = 0.80
    MIN_GP_CLUSTER_CONSISTENCY: float = 1.00
    MIN_GP_OVERALL: float = 0.95

    # Cross-Project Projection thresholds (Sprint I10.6)
    MIN_CROSS_PROJECT_TRANSFER_COVERAGE: float = 0.80
    MIN_CROSS_PROJECT_PROVENANCE_INTEGRITY: float = 1.00
    MIN_CROSS_PROJECT_RELEVANCE_PRECISION: float = 0.50
    MIN_CROSS_PROJECT_ISOLATION: float = 1.00
    MIN_CROSS_PROJECT_DETERMINISM: float = 1.00
    MIN_CROSS_PROJECT_TRANSFERABILITY_ENFORCEMENT: float = 1.00
    MIN_CROSS_PROJECT_OVERALL: float = 0.95

    # Organization Projection thresholds (Sprint I11)
    MIN_ORG_LINEAGE_COMPLETENESS: float = 0.80
    MIN_ORG_PROVENANCE_CHAIN: float = 1.00
    MIN_ORG_CONTRADICTION_DETECTION: float = 0.90
    MIN_ORG_TELEMETRY_ACCURACY: float = 1.00
    MIN_ORG_ISOLATION: float = 1.00
    MIN_ORG_DETERMINISM: float = 1.00
    MIN_ORG_LINEAGE_REPLAYABILITY: float = 1.00
    MIN_ORG_OVERALL: float = 0.95

    # Organization Graph Projection thresholds (Sprint I13)
    MIN_ORG_GRAPH_CONNECTIVITY: float = 0.60
    MIN_ORG_GRAPH_REFERENTIAL_INTEGRITY: float = 1.00
    MIN_ORG_GRAPH_DETERMINISM: float = 1.00
    MIN_ORG_GRAPH_EDGE_COMPLETENESS: float = 0.90
    MIN_ORG_GRAPH_CLUSTER_CONSISTENCY: float = 1.00
    MIN_ORG_GRAPH_METADATA_ACCURACY: float = 1.00
    MIN_ORG_GRAPH_FLOW_BALANCE_ACCURACY: float = 1.00
    MIN_ORG_GRAPH_OVERALL: float = 0.95

    # Hybrid Retrieval Orchestrator thresholds (Sprint I12)
    MIN_I12_INTENT_ACCURACY: float = 0.80
    MIN_I12_PROJECTION_SELECTION: float = 0.90
    MIN_I12_PROJECTION_EFFICIENCY: float = 0.80
    MIN_I12_CONTEXT_WEIGHT_ACCURACY: float = 0.80
    MIN_I12_DETERMINISM: float = 1.00
    MIN_I12_AVAILABILITY_HANDLING: float = 0.90
    MIN_I12_OVERALL: float = 0.85

    # Organization Continuation thresholds (Sprint I14)
    MIN_ORG_CONT_ACTIVITY_COVERAGE: float = 0.50
    MIN_ORG_CONT_TRANSFER_DETECTION: float = 0.80
    MIN_ORG_CONT_CONFLICT_DETECTION: float = 0.80
    MIN_ORG_CONT_ATTENTION_ACCURACY: float = 0.70
    MIN_ORG_CONT_DETERMINISM: float = 1.00
    MIN_ORG_CONT_NEXT_ACTIONS_RELEVANCE: float = 0.70
    MIN_ORG_CONT_ACTIVITY_REPLAYABILITY: float = 1.00
    MIN_ORG_CONT_OVERALL: float = 0.75

    # Recommendation Engine thresholds (Sprint I15)
    MIN_I15_COVERAGE: float = 0.80
    MIN_I15_PRECISION: float = 1.00
    MIN_I15_CATEGORY_EXCLUSIVITY: float = 1.00
    MIN_I15_EVIDENCE_INTEGRITY: float = 1.00
    MIN_I15_PRIORITY_ACCURACY: float = 1.00
    MIN_I15_DETERMINISM: float = 1.00
    MIN_I15_REPLAYABILITY: float = 1.00
    MIN_I15_OVERALL: float = 0.90


# Cognitive Continuity Score weights (configurable for future expansion)
CCS_WEIGHTS: dict[str, float] = {
    "continuation": 0.4,
    "knowledge": 0.3,
    "graph": 0.3,
}


@dataclass
class ExecutionThresholds:
    profile_name: str = "default"
    min_success_rate: float = 0.95
    max_timeout_rate: float = 0.05
    max_denial_rate: float = 0.05
    min_overall_score: float = 0.95
