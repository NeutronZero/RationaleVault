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
