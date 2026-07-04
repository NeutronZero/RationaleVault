"""
RationaleVault Cognitive Head — Decision Synthesis.

Phase 1 — Candidate Generation  (CandidateGenerator)
    Belief → list[DecisionCandidate]

Phase 2 — Synthesis              (SynthesisEngine)
    list[DecisionCandidate] → SynthesisReport

Design rules:
  - Pure functional. No I/O. No side effects.
  - All IDs are deterministic (CAND-[hash], SYN-[hash]).
  - Presentation strings (e.g. "Affirm: X") are intentionally ABSENT.
    They belong in the compiler / delivery layer, not in state.
  - Priority is derived from impact × confidence.
    Impact is computed independently of confidence so a high-confidence
    minor belief never outranks a moderate-confidence critical one.
  - A single Belief may produce multiple DecisionCandidates (future-ready).
    The current implementation produces exactly one candidate per belief.
  - ReasoningReport is consumed read-only; it is never mutated.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

from rationalevault.cognitive_head.belief import Belief
from rationalevault.cognitive_head.reasoning_report import ReasoningReport
from rationalevault.knowledge.contradiction import ContradictionFinding


# ── Enumerations ───────────────────────────────────────────────────────────────

class SynthesisCategory(str, Enum):
    """What type of action is implied by this belief."""
    AFFIRM = "AFFIRM"        # High confidence, no active contradictions — confirm and document
    CHALLENGE = "CHALLENGE"  # Active contradictions, sufficient confidence — flag for resolution
    RESOLVE = "RESOLVE"      # Active contradictions, insufficient confidence — needs resolution
    DEFER = "DEFER"          # Low confidence — insufficient evidence; do not act yet
    MONITOR = "MONITOR"      # Intermediate zone — watch for changes


class SynthesisPriority(str, Enum):
    """Urgency level derived from impact × confidence, not from confidence alone."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class DecisionReason(str, Enum):
    """
    Explains *why* a belief received its category and priority.

    Every DecisionCandidate carries one or more reasons, making each
    decision fully explainable without inspecting raw confidence numbers.
    """
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    MODERATE_CONFIDENCE = "MODERATE_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    ACTIVE_CONTRADICTION = "ACTIVE_CONTRADICTION"
    STALE = "STALE"
    DEPENDENCY_DEGRADED = "DEPENDENCY_DEGRADED"
    HIGH_CORROBORATION = "HIGH_CORROBORATION"


# ── Priority ordering (lower number = higher urgency) ──────────────────────────

_PRIORITY_ORDER: dict[SynthesisPriority, int] = {
    SynthesisPriority.CRITICAL: 0,
    SynthesisPriority.HIGH: 1,
    SynthesisPriority.NORMAL: 2,
    SynthesisPriority.LOW: 3,
}


# ── Configuration ──────────────────────────────────────────────────────────────

@dataclass
class SynthesisConfig:
    """
    Parameters governing synthesis behaviour.

    All category and priority thresholds are derived exclusively from this
    config — no hidden constants exist inside CandidateGenerator or
    SynthesisEngine.  Changing version produces new SYN-[hash] IDs.
    """
    version: str = "1.0"

    # Category thresholds
    affirm_threshold: float = 0.80       # confidence >= this AND no contradictions → AFFIRM
    challenge_threshold: float = 0.50    # contradiction present AND confidence >= this → CHALLENGE
    defer_threshold: float = 0.40        # confidence < this → DEFER
    # RESOLVE: contradiction present AND confidence < challenge_threshold
    # MONITOR: no contradiction AND defer_threshold <= confidence < affirm_threshold

    # Priority urgency bands (applied to impact × confidence product)
    critical_urgency: float = 0.72
    high_urgency: float = 0.48
    normal_urgency: float = 0.24

    # Impact computation weights
    impact_corroboration_weight: float = 0.50
    impact_breadth_weight: float = 0.30
    impact_diversity_weight: float = 0.20
    impact_breadth_divisor: float = 5.0  # normalise supporting_evidence count against this


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DecisionCandidate:
    """
    A raw candidate action derived from a single Belief.

    This is the output of Phase 1 (Candidate Generation).
    Presentation strings are intentionally absent — those live in the
    compiler/delivery layer.  A Belief may produce multiple candidates in
    future sprints; this structure supports that via list[DecisionCandidate].
    """
    candidate_id: str              # CAND-[hash] derived from (belief_id, category, config.version)
    belief_id: str
    category: SynthesisCategory
    reasons: list[DecisionReason]  # explains why this category and priority were chosen
    confidence: float              # verbatim from Belief.final_confidence — NOT re-scored
    impact: float                  # deterministic heuristic; independent of confidence
    priority: SynthesisPriority    # derived from impact × confidence via urgency bands
    contradiction_ids: list[str]   # active contradiction IDs touching this belief's evidence
    belief_title: str              # raw belief title — NOT a presentation string like "Affirm: X"
    belief_content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "belief_id": self.belief_id,
            "category": self.category.value,
            "reasons": [r.value for r in self.reasons],
            "confidence": round(self.confidence, 4),
            "impact": round(self.impact, 4),
            "priority": self.priority.value,
            "contradiction_ids": self.contradiction_ids,
            "belief_title": self.belief_title,
            "belief_content": self.belief_content,
        }


@dataclass(frozen=True)
class SynthesisItem:
    """
    A ranked candidate with a stable SYN-[hash] ID.

    This is the output of Phase 2 (Synthesis).  synthesis_id is derived from
    (candidate_id, SynthesisConfig.version) so that config changes produce
    new IDs even for identical underlying beliefs.
    """
    synthesis_id: str          # SYN-[hash]
    candidate: DecisionCandidate

    # ── Property shortcuts (mirror candidate fields for call-site ergonomics) ──

    @property
    def belief_id(self) -> str:
        return self.candidate.belief_id

    @property
    def category(self) -> SynthesisCategory:
        return self.candidate.category

    @property
    def priority(self) -> SynthesisPriority:
        return self.candidate.priority

    @property
    def confidence(self) -> float:
        return self.candidate.confidence

    @property
    def impact(self) -> float:
        return self.candidate.impact

    @property
    def contradiction_ids(self) -> list[str]:
        return self.candidate.contradiction_ids

    @property
    def belief_title(self) -> str:
        return self.candidate.belief_title

    @property
    def reasons(self) -> list[DecisionReason]:
        return self.candidate.reasons

    def to_dict(self) -> dict[str, Any]:
        return {
            "synthesis_id": self.synthesis_id,
            **self.candidate.to_dict(),
        }


@dataclass(frozen=True)
class SynthesisReport:
    """Immutable, ordered collection of synthesis items."""
    items: list[SynthesisItem]   # sorted by priority (CRITICAL first) then confidence DESC
    summary: dict[str, Any]
    synthesis_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [i.to_dict() for i in self.items],
            "summary": self.summary,
            "synthesis_version": self.synthesis_version,
        }


# ── Phase 1: Candidate Generation ─────────────────────────────────────────────

class CandidateGenerator:
    """
    Phase 1: Generates DecisionCandidates from Beliefs.

    Contract:
      - generate(belief, ...) → list[DecisionCandidate]
      - Currently returns a list of exactly one candidate per belief.
      - Returning a list ensures the caller handles one-to-many naturally.
    """

    @staticmethod
    def _compute_impact(belief: Belief, config: SynthesisConfig) -> float:
        """
        Deterministic impact heuristic.

        Impact is derived from evidence *breadth* (corroboration, source count,
        diversity) independently of confidence so that a high-confidence
        minor belief does not automatically outrank a lower-confidence but
        critical one.
        """
        corroboration = belief.assessment.corroboration_score
        evidence_breadth = min(1.0, len(belief.supporting_evidence) / config.impact_breadth_divisor)
        diversity = belief.assessment.agreement_score
        impact = (
            corroboration * config.impact_corroboration_weight
            + evidence_breadth * config.impact_breadth_weight
            + diversity * config.impact_diversity_weight
        )
        return round(min(1.0, max(0.0, impact)), 4)

    @staticmethod
    def _derive_priority(impact: float, confidence: float, config: SynthesisConfig) -> SynthesisPriority:
        """Priority = f(impact × confidence) mapped against urgency bands."""
        urgency = impact * confidence
        if urgency >= config.critical_urgency:
            return SynthesisPriority.CRITICAL
        elif urgency >= config.high_urgency:
            return SynthesisPriority.HIGH
        elif urgency >= config.normal_urgency:
            return SynthesisPriority.NORMAL
        return SynthesisPriority.LOW

    @staticmethod
    def _classify(
        belief: Belief,
        active_contradiction_ids: set[str],
        config: SynthesisConfig,
    ) -> tuple[SynthesisCategory, list[DecisionReason]]:
        """Classify a belief into a SynthesisCategory and collect DecisionReasons."""
        confidence = belief.final_confidence
        has_contradictions = len(active_contradiction_ids) > 0
        is_stale = belief.assessment.staleness_penalty > 0.1
        is_degraded = belief.assessment.propagated_adjustment < -0.05
        is_well_corroborated = belief.assessment.corroboration_score >= 0.15

        reasons: list[DecisionReason] = []

        # Collect condition reasons (order-independent)
        if has_contradictions:
            reasons.append(DecisionReason.ACTIVE_CONTRADICTION)
        if is_stale:
            reasons.append(DecisionReason.STALE)
        if is_degraded:
            reasons.append(DecisionReason.DEPENDENCY_DEGRADED)
        if is_well_corroborated:
            reasons.append(DecisionReason.HIGH_CORROBORATION)

        # Category classification (mutually exclusive, priority order)
        if confidence < config.defer_threshold:
            reasons.append(DecisionReason.LOW_CONFIDENCE)
            return SynthesisCategory.DEFER, reasons

        if has_contradictions:
            if confidence >= config.challenge_threshold:
                return SynthesisCategory.CHALLENGE, reasons
            return SynthesisCategory.RESOLVE, reasons

        if confidence >= config.affirm_threshold:
            reasons.append(DecisionReason.HIGH_CONFIDENCE)
            return SynthesisCategory.AFFIRM, reasons

        # Intermediate zone: no contradictions, defer_threshold ≤ confidence < affirm_threshold
        reasons.append(DecisionReason.MODERATE_CONFIDENCE)
        return SynthesisCategory.MONITOR, reasons

    @staticmethod
    def _generate_candidate_id(belief_id: str, category: SynthesisCategory, version: str) -> str:
        data = f"candidate:{belief_id}:{category.value}:{version}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"CAND-{h}"

    @staticmethod
    def generate(
        belief: Belief,
        active_contradiction_ids: set[str],
        config: SynthesisConfig,
    ) -> list[DecisionCandidate]:
        """
        Generate candidates for a single belief.

        Returns a list to support one-belief → many-candidate in future sprints.
        Currently returns exactly one candidate per belief.
        """
        category, reasons = CandidateGenerator._classify(belief, active_contradiction_ids, config)
        impact = CandidateGenerator._compute_impact(belief, config)
        priority = CandidateGenerator._derive_priority(impact, belief.final_confidence, config)
        candidate_id = CandidateGenerator._generate_candidate_id(
            belief.belief_id, category, config.version
        )
        return [
            DecisionCandidate(
                candidate_id=candidate_id,
                belief_id=belief.belief_id,
                category=category,
                reasons=reasons,
                confidence=belief.final_confidence,
                impact=impact,
                priority=priority,
                contradiction_ids=sorted(active_contradiction_ids),
                belief_title=belief.title,
                belief_content=belief.content,
            )
        ]


# ── Phase 2: Synthesis ─────────────────────────────────────────────────────────

class SynthesisEngine:
    """
    Phase 2: Ranks and groups all candidates into a SynthesisReport.

    synthesis_id is derived from (candidate_id, config.version) so that
    changing SynthesisConfig produces new stable IDs even for otherwise
    identical candidates.

    This engine consumes a ReasoningReport read-only.  It never mutates
    beliefs, assessments, contradictions, or the report itself.
    """

    @staticmethod
    def _generate_synthesis_id(candidate_id: str, config_version: str) -> str:
        data = f"synthesis:{candidate_id}:{config_version}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"SYN-{h}"

    @staticmethod
    def _active_contradiction_ids_for_belief(
        belief: Belief,
        contradictions: list[ContradictionFinding],
    ) -> set[str]:
        """Find active (non-suppressed) contradiction IDs touching this belief's evidence."""
        evidence_ids = set(belief.supporting_evidence)
        return {
            c.finding_id
            for c in contradictions
            if not getattr(c, "suppressed", False)
            and (c.rule_a_id in evidence_ids or c.rule_b_id in evidence_ids)
        }

    @staticmethod
    def synthesize(
        report: ReasoningReport,
        config: SynthesisConfig = SynthesisConfig(),
    ) -> SynthesisReport:
        """
        Consume a ReasoningReport and produce a SynthesisReport.

        Steps:
          1. For each Belief, find its active contradictions.
          2. Generate one or more DecisionCandidates (Phase 1).
          3. Wrap each candidate in a SynthesisItem with a stable SYN-[hash].
          4. Sort by priority (CRITICAL first) then confidence descending.
          5. Build summary counts.
        """
        contradictions = report.contradictions
        items: list[SynthesisItem] = []

        for belief in report.beliefs:
            active_ids = SynthesisEngine._active_contradiction_ids_for_belief(
                belief, contradictions
            )
            candidates = CandidateGenerator.generate(belief, active_ids, config)
            for candidate in candidates:
                syn_id = SynthesisEngine._generate_synthesis_id(
                    candidate.candidate_id, config.version
                )
                items.append(SynthesisItem(synthesis_id=syn_id, candidate=candidate))

        # Sort: priority band first, then confidence descending within band
        items.sort(key=lambda i: (_PRIORITY_ORDER[i.priority], -i.confidence))

        # Build summary
        category_counts: dict[str, int] = {c.value: 0 for c in SynthesisCategory}
        priority_counts: dict[str, int] = {p.value: 0 for p in SynthesisPriority}
        for item in items:
            category_counts[item.category.value] += 1
            priority_counts[item.priority.value] += 1

        summary: dict[str, Any] = {
            "total_candidates": len(items),
            "by_category": category_counts,
            "by_priority": priority_counts,
        }

        return SynthesisReport(
            items=items,
            summary=summary,
            synthesis_version=config.version,
        )
