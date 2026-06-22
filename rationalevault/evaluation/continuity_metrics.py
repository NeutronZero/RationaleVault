from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IdentityStatus(str, Enum):
    PRESERVED = "PRESERVED"
    ALIASED = "ALIASED"
    LOST = "LOST"


class SemanticStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    DRIFTED = "DRIFTED"
    CONTRADICTED = "CONTRADICTED"


class DecisionIntegrityState(str, Enum):
    HEALTHY = "HEALTHY"
    MUTATED = "MUTATED"
    CONTRADICTED = "CONTRADICTED"
    LOST = "LOST"


SEVERITY_WEIGHTS = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
    "critical": 5.0,
}


@dataclass
class MetricSummary:
    goal_recall: float = 0.0
    task_recall: float = 0.0
    decision_recall: float = 0.0
    question_recall: float = 0.0
    blocker_recall: float = 0.0
    next_action_accuracy: float = 0.0
    rationale_recall: float = 0.0

    # Integrity
    decision_contradiction_rate: float = 0.0
    overall_decision_integrity: float = 1.0
    weighted_decision_integrity: float = 1.0
    weighted_contradiction_rate: float = 0.0

    # Fidelity / Drift
    decision_drift: float = 0.0
    goal_drift: float = 0.0
    next_action_drift: float = 0.0

    overall_continuity: float = 0.0
    overall_fidelity: float = 0.0

    # Detailed status mapping per decision
    decision_states: list[dict[str, Any]] = field(default_factory=list)

    # Agent-level breakout metrics: agent_name -> MetricSummary
    agent_breakout: dict[str, MetricSummary] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_recall": self.goal_recall,
            "task_recall": self.task_recall,
            "decision_recall": self.decision_recall,
            "question_recall": self.question_recall,
            "blocker_recall": self.blocker_recall,
            "next_action_accuracy": self.next_action_accuracy,
            "rationale_recall": self.rationale_recall,
            "decision_contradiction_rate": self.decision_contradiction_rate,
            "overall_decision_integrity": self.overall_decision_integrity,
            "weighted_decision_integrity": self.weighted_decision_integrity,
            "weighted_contradiction_rate": self.weighted_contradiction_rate,
            "decision_drift": self.decision_drift,
            "goal_drift": self.goal_drift,
            "next_action_drift": self.next_action_drift,
            "overall_continuity": self.overall_continuity,
            "overall_fidelity": self.overall_fidelity,
            "decision_states": self.decision_states,
            "agent_breakout": {
                name: summary.to_dict() for name, summary in self.agent_breakout.items()
            },
        }


def calculate_recall(expected: list[str], observed: list[str]) -> float:
    if not expected:
        return 1.0
    exp_set = {e.strip().lower() for e in expected}
    obs_set = {o.strip().lower() for o in observed}
    matched = exp_set.intersection(obs_set)
    return len(matched) / len(exp_set)


def calculate_drift(expected: list[str], observed: list[str]) -> float:
    if not observed:
        return 0.0
    exp_set = {e.strip().lower() for e in expected}
    obs_set = {o.strip().lower() for o in observed}
    drifted = obs_set - exp_set
    return len(drifted) / len(obs_set)


def get_jaccard_similarity(s1: str, s2: str) -> float:
    w1 = set(re_words(s1.lower()))
    w2 = set(re_words(s2.lower()))
    if not w1 or not w2:
        return 0.0
    return len(w1.intersection(w2)) / len(w1.union(w2))


def re_words(text: str) -> list[str]:
    import re
    return re.findall(r"\b\w+\b", text)


def detect_contradiction(s1: str, s2: str) -> bool:
    s1_l, s2_l = s1.lower(), s2.lower()
    # SQLite vs Postgres contradiction
    if ("sqlite" in s1_l and "postgres" in s2_l) or ("postgres" in s1_l and "sqlite" in s2_l):
        return True
    # FastAPI vs Flask contradiction
    if ("fastapi" in s1_l and "flask" in s2_l) or ("flask" in s1_l and "fastapi" in s2_l):
        return True
    # Negation check
    negations = ["not", "never", "no longer", "don't"]
    for neg in negations:
        if (neg in s1_l and neg not in s2_l) or (neg in s2_l and neg not in s1_l):
            # If word similarity is otherwise high, it's a semantic inversion contradiction
            if get_jaccard_similarity(s1, s2) > 0.4:
                return True
    return False


def resolve_decision_state(
    expected: str,
    observed_list: list[str],
) -> tuple[IdentityStatus, SemanticStatus, DecisionIntegrityState, str]:
    exp_clean = expected.strip().lower()
    
    # Perfect Match
    for obs in observed_list:
        if obs.strip().lower() == exp_clean:
            return IdentityStatus.PRESERVED, SemanticStatus.CONSISTENT, DecisionIntegrityState.HEALTHY, obs

    # Find best fuzzy match candidate
    best_similarity = 0.0
    best_candidate = ""
    for obs in observed_list:
        sim = get_jaccard_similarity(expected, obs)
        if sim > best_similarity:
            best_similarity = sim
            best_candidate = obs

    # Evaluate matches based on similarity
    if best_similarity >= 0.7:
        if detect_contradiction(expected, best_candidate):
            return IdentityStatus.ALIASED, SemanticStatus.CONTRADICTED, DecisionIntegrityState.CONTRADICTED, best_candidate
        return IdentityStatus.ALIASED, SemanticStatus.CONSISTENT, DecisionIntegrityState.HEALTHY, best_candidate
    elif best_similarity >= 0.4:
        if detect_contradiction(expected, best_candidate):
            return IdentityStatus.ALIASED, SemanticStatus.CONTRADICTED, DecisionIntegrityState.CONTRADICTED, best_candidate
        return IdentityStatus.ALIASED, SemanticStatus.DRIFTED, DecisionIntegrityState.MUTATED, best_candidate
    
    # Lost or Contradicted
    for obs in observed_list:
        if detect_contradiction(expected, obs):
            return IdentityStatus.LOST, SemanticStatus.CONTRADICTED, DecisionIntegrityState.CONTRADICTED, obs

    return IdentityStatus.LOST, SemanticStatus.CONSISTENT, DecisionIntegrityState.LOST, ""


def compute_metrics(
    expected_goal: str,
    observed_goal: str,
    expected_tasks: list[str],
    observed_tasks: list[str],
    expected_decisions: list[str] | list[dict[str, Any]],
    observed_decisions: list[str],
    expected_questions: list[str],
    observed_questions: list[str],
    expected_blockers: list[str],
    observed_blockers: list[str],
    expected_next_action: str,
    observed_next_action: str,
    expected_rationales: list[str] = None,
    observed_rationales: list[str] = None,
) -> MetricSummary:
    goal_recall = 1.0 if expected_goal.strip().lower() in observed_goal.strip().lower() else 0.0
    task_recall = calculate_recall(expected_tasks, observed_tasks)
    question_recall = calculate_recall(expected_questions, observed_questions)
    blocker_recall = calculate_recall(expected_blockers, observed_blockers)
    next_action_accuracy = 1.0 if expected_next_action.strip().lower() == observed_next_action.strip().lower() else 0.0
    rationale_recall = calculate_recall(expected_rationales or [], observed_rationales or [])

    # Integrity metrics
    decision_states = []
    total_score = 0.0
    unweighted_score_sum = 0.0
    total_weight = 0.0
    contradicted_count = 0
    weighted_contradiction_sum = 0.0

    score_mappings = {
        DecisionIntegrityState.HEALTHY: 1.0,
        DecisionIntegrityState.MUTATED: 0.5,
        DecisionIntegrityState.LOST: 0.25,
        DecisionIntegrityState.CONTRADICTED: 0.0,
    }

    # Normalize expected decisions (they could be dicts with severity or just strings)
    exp_dec_strings = []
    for d in expected_decisions:
        if isinstance(d, dict):
            exp_dec_strings.append(d["decision"])
        else:
            exp_dec_strings.append(d)

    # Normalize observed decisions (handles dicts in simulated runs)
    obs_dec_strings = []
    for d in observed_decisions:
        if isinstance(d, dict):
            obs_dec_strings.append(d["decision"])
        else:
            obs_dec_strings.append(d)

    decision_recall = calculate_recall(exp_dec_strings, obs_dec_strings)

    for d in expected_decisions:
        if isinstance(d, dict):
            text = d["decision"]
            severity = d.get("severity", "medium").lower()
        else:
            text = d
            severity = "medium"

        weight = SEVERITY_WEIGHTS.get(severity, 2.0)
        identity, semantic, state, obs_text = resolve_decision_state(text, obs_dec_strings)
        
        score = score_mappings[state]
        unweighted_score_sum += score
        total_score += (score * weight)
        total_weight += weight

        is_contradicted = (state == DecisionIntegrityState.CONTRADICTED)
        if is_contradicted:
            contradicted_count += 1
            weighted_contradiction_sum += weight

        decision_states.append({
            "expected": text,
            "severity": severity,
            "identity_status": identity.value,
            "semantic_status": semantic.value,
            "integrity_state": state.value,
            "observed": obs_text,
        })

    overall_decision_integrity = unweighted_score_sum / len(expected_decisions) if expected_decisions else 1.0
    weighted_decision_integrity = total_score / total_weight if total_weight > 0 else 1.0
    decision_contradiction_rate = contradicted_count / len(expected_decisions) if expected_decisions else 0.0
    weighted_contradiction_rate = weighted_contradiction_sum / total_weight if total_weight > 0 else 0.0

    # Fidelity / Drift
    goal_drift = 0.0 if goal_recall == 1.0 else 1.0
    decision_drift = calculate_drift(exp_dec_strings, obs_dec_strings)
    next_action_drift = 0.0 if next_action_accuracy == 1.0 else 1.0

    overall_continuity = (goal_recall + task_recall + weighted_decision_integrity + question_recall + rationale_recall) / 5.0
    overall_fidelity = 1.0 - ((goal_drift + decision_drift + next_action_drift) / 3.0)

    return MetricSummary(
        goal_recall=goal_recall,
        task_recall=task_recall,
        decision_recall=decision_recall,
        question_recall=question_recall,
        blocker_recall=blocker_recall,
        next_action_accuracy=next_action_accuracy,
        rationale_recall=rationale_recall,
        decision_contradiction_rate=decision_contradiction_rate,
        overall_decision_integrity=overall_decision_integrity,
        weighted_decision_integrity=weighted_decision_integrity,
        weighted_contradiction_rate=weighted_contradiction_rate,
        decision_drift=decision_drift,
        goal_drift=goal_drift,
        next_action_drift=next_action_drift,
        overall_continuity=overall_continuity,
        overall_fidelity=overall_fidelity,
        decision_states=decision_states,
    )
