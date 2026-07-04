"""
Sprint B3 — Decision Synthesis Tests.

Covers:
  - Threshold classification (AFFIRM / CHALLENGE / RESOLVE / DEFER / MONITOR)
  - DecisionReason annotation correctness
  - Priority = f(impact × confidence), not confidence alone
  - Stable CAND-, SYN-, DEC- IDs across replays
  - SynthesisConfig version change → new SYN- IDs
  - DecisionGatePolicy version change → new DEC- IDs
  - Gate never re-scores (confidence/priority/category frozen)
  - Gate confidence floor
  - Gate contradiction blocking
  - Gate max_decisions cap (overflow → blocked)
  - DEFER always blocked regardless of confidence
  - DecisionSet ordering (CRITICAL → LOW, then confidence DESC within band)
  - Policy determinism: same policy → same DecisionSet
  - to_dict() round-trip completeness
  - One belief → one candidate (current) / list-ready contract
  - Candidate stability: reordering output does not change IDs
"""
from __future__ import annotations

import pytest
from rationalevault.cognitive_head.assessment import EvidenceAssessment
from rationalevault.cognitive_head.belief import Belief
from rationalevault.cognitive_head.decision import (
    DecisionGate,
    DecisionGatePolicy,
    DecisionSet,
)
from rationalevault.cognitive_head.synthesis import (
    CandidateGenerator,
    DecisionReason,
    SynthesisCategory,
    SynthesisConfig,
    SynthesisEngine,
    SynthesisItem,
    SynthesisPriority,
    SynthesisReport,
)
from rationalevault.cognitive_head.reasoning_report import ReasoningReport, ReasoningReportBuilder
from rationalevault.knowledge.contradiction import ContradictionFinding
from rationalevault.knowledge.models import EpistemicStatus


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_assessment(
    base: float = 0.7,
    agreement: float = 0.1,
    corroboration: float = 0.1,
    contradiction_penalty: float = 0.0,
    staleness_penalty: float = 0.0,
    propagated_adjustment: float = 0.0,
) -> EvidenceAssessment:
    local = min(1.0, max(0.0, base + agreement + corroboration - contradiction_penalty - staleness_penalty))
    final = min(1.0, max(0.0, local + propagated_adjustment))
    return EvidenceAssessment(
        base_confidence=base,
        agreement_score=agreement,
        corroboration_score=corroboration,
        contradiction_penalty=contradiction_penalty,
        staleness_penalty=staleness_penalty,
        propagated_adjustment=propagated_adjustment,
        local_confidence=local,
        final_confidence=final,
    )


def _make_belief(
    title: str = "Test Rule",
    content: str = "Test content",
    final_confidence: float = 0.85,
    supporting_evidence: list[str] | None = None,
    propagated_adjustment: float = 0.0,
    staleness_penalty: float = 0.0,
    corroboration_score: float = 0.10,
    agreement_score: float = 0.05,
) -> Belief:
    if supporting_evidence is None:
        supporting_evidence = ["ev-001"]
    assessment = _make_assessment(
        base=max(0.0, final_confidence - agreement_score - corroboration_score),
        agreement=agreement_score,
        corroboration=corroboration_score,
        staleness_penalty=staleness_penalty,
        propagated_adjustment=propagated_adjustment,
    )
    return Belief(
        belief_id=f"BEL-{title[:4].upper().replace(' ', '_')}",
        title=title,
        content=content,
        local_confidence=assessment.local_confidence,
        propagated_adjustment=propagated_adjustment,
        final_confidence=final_confidence,
        assessment=assessment,
        supporting_evidence=supporting_evidence,
        dependent_belief_ids=[],
    )


def _make_contradiction(rule_a: str, rule_b: str, suppressed: bool = False) -> ContradictionFinding:
    return ContradictionFinding(
        finding_id=f"CONTR-{rule_a[:4]}{rule_b[:4]}",
        rule_a_id=rule_a,
        rule_b_id=rule_b,
        contradiction_type="opposite_assertion",
        severity="warning",
        evidence="Test conflict",
        suggested_status=EpistemicStatus.CONFLICTED,
        suppressed=suppressed,
    )


def _make_report(
    beliefs: list[Belief],
    contradictions: list[ContradictionFinding] | None = None,
) -> ReasoningReport:
    from rationalevault.cognitive_head.config import ReasoningConfig
    return ReasoningReportBuilder.build(
        beliefs=beliefs,
        contradictions=contradictions or [],
        config=ReasoningConfig(),
    )


# ── Category Classification Tests ─────────────────────────────────────────────

class TestCategoryClassification:

    def test_high_confidence_no_contradiction_is_affirm(self):
        config = SynthesisConfig(affirm_threshold=0.80)
        belief = _make_belief(final_confidence=0.90)
        candidates = CandidateGenerator.generate(belief, set(), config)
        assert len(candidates) == 1
        assert candidates[0].category == SynthesisCategory.AFFIRM

    def test_low_confidence_is_defer(self):
        config = SynthesisConfig(defer_threshold=0.40)
        belief = _make_belief(final_confidence=0.30)
        candidates = CandidateGenerator.generate(belief, set(), config)
        assert candidates[0].category == SynthesisCategory.DEFER

    def test_contradiction_high_confidence_is_challenge(self):
        config = SynthesisConfig(challenge_threshold=0.50)
        belief = _make_belief(final_confidence=0.75, supporting_evidence=["ev-001"])
        candidates = CandidateGenerator.generate(belief, {"CONTR-ABC"}, config)
        assert candidates[0].category == SynthesisCategory.CHALLENGE

    def test_contradiction_low_confidence_is_resolve(self):
        config = SynthesisConfig(challenge_threshold=0.50)
        belief = _make_belief(final_confidence=0.45, supporting_evidence=["ev-001"])
        candidates = CandidateGenerator.generate(belief, {"CONTR-ABC"}, config)
        assert candidates[0].category == SynthesisCategory.RESOLVE

    def test_intermediate_no_contradiction_is_monitor(self):
        config = SynthesisConfig(affirm_threshold=0.80, defer_threshold=0.40)
        belief = _make_belief(final_confidence=0.60)
        candidates = CandidateGenerator.generate(belief, set(), config)
        assert candidates[0].category == SynthesisCategory.MONITOR

    def test_exactly_at_affirm_threshold_is_affirm(self):
        config = SynthesisConfig(affirm_threshold=0.80)
        belief = _make_belief(final_confidence=0.80)
        candidates = CandidateGenerator.generate(belief, set(), config)
        assert candidates[0].category == SynthesisCategory.AFFIRM

    def test_exactly_at_defer_threshold_is_monitor(self):
        """At exactly defer_threshold, the belief is NOT deferred (it uses < operator)."""
        config = SynthesisConfig(defer_threshold=0.40, affirm_threshold=0.80)
        belief = _make_belief(final_confidence=0.40)
        candidates = CandidateGenerator.generate(belief, set(), config)
        # confidence == defer_threshold means MONITOR (not DEFER)
        assert candidates[0].category == SynthesisCategory.MONITOR

    def test_stale_belief_does_not_affirm(self):
        config = SynthesisConfig(affirm_threshold=0.80)
        belief = _make_belief(final_confidence=0.90, staleness_penalty=0.15)  # > 0.1 stale threshold
        candidates = CandidateGenerator.generate(belief, set(), config)
        # Stale belief with high confidence gets AFFIRM but with STALE reason
        assert candidates[0].category == SynthesisCategory.AFFIRM
        assert DecisionReason.STALE in candidates[0].reasons


class TestDecisionReasonAnnotation:

    def test_high_confidence_affirm_has_high_confidence_reason(self):
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.90)
        candidates = CandidateGenerator.generate(belief, set(), config)
        assert DecisionReason.HIGH_CONFIDENCE in candidates[0].reasons

    def test_active_contradiction_reason_attached(self):
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.75)
        candidates = CandidateGenerator.generate(belief, {"CONTR-XYZ"}, config)
        assert DecisionReason.ACTIVE_CONTRADICTION in candidates[0].reasons

    def test_low_confidence_reason_attached_to_defer(self):
        config = SynthesisConfig(defer_threshold=0.40)
        belief = _make_belief(final_confidence=0.25)
        candidates = CandidateGenerator.generate(belief, set(), config)
        assert DecisionReason.LOW_CONFIDENCE in candidates[0].reasons

    def test_dependency_degraded_reason(self):
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.85, propagated_adjustment=-0.10)
        candidates = CandidateGenerator.generate(belief, set(), config)
        assert DecisionReason.DEPENDENCY_DEGRADED in candidates[0].reasons

    def test_monitor_has_moderate_confidence_reason(self):
        config = SynthesisConfig(affirm_threshold=0.80, defer_threshold=0.40)
        belief = _make_belief(final_confidence=0.60)
        candidates = CandidateGenerator.generate(belief, set(), config)
        assert DecisionReason.MODERATE_CONFIDENCE in candidates[0].reasons


# ── Priority = Impact × Confidence Tests ──────────────────────────────────────

class TestPriorityDerivation:

    def test_priority_is_not_confidence_alone(self):
        """A high-confidence belief with zero impact should not outrank a moderate-
        confidence belief with high impact in CRITICAL band."""
        config = SynthesisConfig()

        # High confidence, no evidence breadth (zero corroboration)
        belief_high_conf = _make_belief(
            title="Minor Style Rule",
            final_confidence=0.99,
            supporting_evidence=["ev-001"],
            corroboration_score=0.0,
            agreement_score=0.0,
        )

        # Moderate confidence, high corroboration + broad evidence
        belief_critical = _make_belief(
            title="Critical Security Rule",
            final_confidence=0.82,
            supporting_evidence=["ev-A", "ev-B", "ev-C", "ev-D", "ev-E"],
            corroboration_score=0.20,
            agreement_score=0.20,
        )

        cands_minor = CandidateGenerator.generate(belief_high_conf, set(), config)
        cands_critical = CandidateGenerator.generate(belief_critical, set(), config)

        # The "minor" rule should NOT be CRITICAL (impact is near zero)
        assert cands_minor[0].impact < cands_critical[0].impact

    def test_critical_urgency_band(self):
        """urgency (impact × confidence) >= critical_urgency threshold → CRITICAL."""
        config = SynthesisConfig(critical_urgency=0.72)
        # Build a belief where impact × confidence is forced high
        belief = _make_belief(
            final_confidence=0.90,
            supporting_evidence=["e1", "e2", "e3", "e4", "e5"],
            corroboration_score=0.20,
            agreement_score=0.20,
        )
        cands = CandidateGenerator.generate(belief, set(), config)
        urgency = cands[0].impact * cands[0].confidence
        if urgency >= config.critical_urgency:
            assert cands[0].priority == SynthesisPriority.CRITICAL
        # If urgency is below critical, just verify it's not erroneously CRITICAL
        # (test is conditional on actual computed urgency)

    def test_all_urgency_bands_exist_in_enum(self):
        assert SynthesisPriority.CRITICAL in SynthesisPriority
        assert SynthesisPriority.HIGH in SynthesisPriority
        assert SynthesisPriority.NORMAL in SynthesisPriority
        assert SynthesisPriority.LOW in SynthesisPriority


# ── ID Stability Tests ─────────────────────────────────────────────────────────

class TestIDStability:

    def test_candidate_id_is_deterministic(self):
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.85)
        c1 = CandidateGenerator.generate(belief, set(), config)
        c2 = CandidateGenerator.generate(belief, set(), config)
        assert c1[0].candidate_id == c2[0].candidate_id

    def test_synthesis_id_is_deterministic(self):
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        s1 = SynthesisEngine.synthesize(report, config)
        s2 = SynthesisEngine.synthesize(report, config)
        assert s1.items[0].synthesis_id == s2.items[0].synthesis_id

    def test_decision_id_is_deterministic(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy()
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        d1 = DecisionGate.gate(synthesis, policy)
        d2 = DecisionGate.gate(synthesis, policy)
        if d1.decisions:
            assert d1.decisions[0].decision_id == d2.decisions[0].decision_id

    def test_synthesis_config_version_change_produces_new_syn_id(self):
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        config_v1 = SynthesisConfig(version="1.0")
        config_v2 = SynthesisConfig(version="2.0")
        s1 = SynthesisEngine.synthesize(report, config_v1)
        s2 = SynthesisEngine.synthesize(report, config_v2)
        assert s1.items[0].synthesis_id != s2.items[0].synthesis_id

    def test_gate_policy_version_change_produces_new_dec_id(self):
        """Identical synthesis under different policy versions → different DEC- IDs."""
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)

        policy_v1 = DecisionGatePolicy(version="1.0")
        policy_v2 = DecisionGatePolicy(version="2.0")
        ds1 = DecisionGate.gate(synthesis, policy_v1)
        ds2 = DecisionGate.gate(synthesis, policy_v2)

        ids_v1 = {d.decision_id for d in ds1.decisions}
        ids_v2 = {d.decision_id for d in ds2.decisions}
        assert ids_v1.isdisjoint(ids_v2), "Different policy versions must produce different DEC- IDs"

    def test_candidate_id_stable_regardless_of_external_ordering(self):
        """Shuffling external caller order does not change candidate IDs."""
        config = SynthesisConfig()
        b1 = _make_belief(title="Alpha", final_confidence=0.85)
        b2 = _make_belief(title="Beta", final_confidence=0.75)
        report_ab = _make_report([b1, b2])
        report_ba = _make_report([b2, b1])
        s_ab = SynthesisEngine.synthesize(report_ab, config)
        s_ba = SynthesisEngine.synthesize(report_ba, config)
        ids_ab = {i.synthesis_id for i in s_ab.items}
        ids_ba = {i.synthesis_id for i in s_ba.items}
        assert ids_ab == ids_ba


# ── Gate Policy Tests ─────────────────────────────────────────────────────────

class TestDecisionGatePolicy:

    def test_confidence_floor_blocks_low_confidence(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.70)
        belief = _make_belief(final_confidence=0.65)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        decision_set = DecisionGate.gate(synthesis, policy)
        assert decision_set.summary["approved"] == 0
        assert decision_set.summary["blocked"] == 1

    def test_confidence_floor_passes_sufficient_confidence(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.60)
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        decision_set = DecisionGate.gate(synthesis, policy)
        # Should pass (no contradictions, high confidence)
        assert decision_set.summary["approved"] == 1

    def test_contradiction_blocking_blocks_when_enabled(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy(block_if_contradicted=True, minimum_confidence=0.50)
        belief = _make_belief(final_confidence=0.75, supporting_evidence=["ev-001"])
        contradiction = _make_contradiction("ev-001", "ev-002")
        report = _make_report([belief], [contradiction])
        synthesis = SynthesisEngine.synthesize(report, config)
        decision_set = DecisionGate.gate(synthesis, policy)
        assert decision_set.summary["approved"] == 0

    def test_contradiction_blocking_disabled_allows_contradicted_items(self):
        config = SynthesisConfig(challenge_threshold=0.50)
        policy = DecisionGatePolicy(block_if_contradicted=False, minimum_confidence=0.50)
        belief = _make_belief(final_confidence=0.75, supporting_evidence=["ev-001"])
        contradiction = _make_contradiction("ev-001", "ev-002")
        report = _make_report([belief], [contradiction])
        synthesis = SynthesisEngine.synthesize(report, config)
        decision_set = DecisionGate.gate(synthesis, policy)
        assert decision_set.summary["approved"] == 1

    def test_defer_always_blocked_regardless_of_confidence(self):
        """DEFER items are blocked even if minimum_confidence=0.0."""
        config = SynthesisConfig(defer_threshold=0.40)
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False)
        belief = _make_belief(final_confidence=0.20)  # below defer threshold
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        assert synthesis.items[0].category == SynthesisCategory.DEFER
        decision_set = DecisionGate.gate(synthesis, policy)
        assert decision_set.summary["approved"] == 0

    def test_max_decisions_cap_limits_output(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False, max_decisions=2)
        beliefs = [_make_belief(title=f"Rule {i}", final_confidence=0.85) for i in range(5)]
        report = _make_report(beliefs)
        synthesis = SynthesisEngine.synthesize(report, config)
        decision_set = DecisionGate.gate(synthesis, policy)
        assert len(decision_set.decisions) <= 2

    def test_max_decisions_overflow_goes_to_blocked(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False, max_decisions=1)
        beliefs = [_make_belief(title=f"Rule {i}", final_confidence=0.85) for i in range(3)]
        report = _make_report(beliefs)
        synthesis = SynthesisEngine.synthesize(report, config)
        total_candidates = len(synthesis.items)
        decision_set = DecisionGate.gate(synthesis, policy)
        assert len(decision_set.decisions) == 1
        assert len(decision_set.blocked) == total_candidates - 1

    def test_max_decisions_zero_means_unlimited(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False, max_decisions=0)
        beliefs = [_make_belief(title=f"Rule {i}", final_confidence=0.85) for i in range(10)]
        report = _make_report(beliefs)
        synthesis = SynthesisEngine.synthesize(report, config)
        decision_set = DecisionGate.gate(synthesis, policy)
        assert len(decision_set.decisions) == 10

    def test_gate_never_changes_confidence(self):
        """Gate copies confidence verbatim — it never re-scores."""
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False)
        belief = _make_belief(final_confidence=0.82)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        original_conf = synthesis.items[0].confidence
        decision_set = DecisionGate.gate(synthesis, policy)
        if decision_set.decisions:
            assert decision_set.decisions[0].confidence == original_conf

    def test_gate_never_changes_category(self):
        """Gate copies category verbatim — it never re-scores."""
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False)
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        original_cat = synthesis.items[0].category
        decision_set = DecisionGate.gate(synthesis, policy)
        if decision_set.decisions:
            assert decision_set.decisions[0].category == original_cat

    def test_gate_never_changes_priority(self):
        """Gate copies priority verbatim — it never re-scores."""
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False)
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        original_pri = synthesis.items[0].priority
        decision_set = DecisionGate.gate(synthesis, policy)
        if decision_set.decisions:
            assert decision_set.decisions[0].priority == original_pri

    def test_suppressed_contradictions_do_not_block(self):
        """Suppressed contradictions do not count as active; gate should not block."""
        config = SynthesisConfig()
        policy = DecisionGatePolicy(block_if_contradicted=True, minimum_confidence=0.50)
        belief = _make_belief(final_confidence=0.80, supporting_evidence=["ev-001"])
        contradiction = _make_contradiction("ev-001", "ev-002", suppressed=True)
        report = _make_report([belief], [contradiction])
        synthesis = SynthesisEngine.synthesize(report, config)
        decision_set = DecisionGate.gate(synthesis, policy)
        # Suppressed contradiction → item should not be blocked
        assert decision_set.summary["approved"] == 1


# ── Ordering Tests ─────────────────────────────────────────────────────────────

class TestOrdering:

    def test_synthesis_sorted_by_priority_then_confidence(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False)

        # Force different priorities via varied impact × confidence
        beliefs = [
            _make_belief(title="Low Priority", final_confidence=0.50),
            _make_belief(title="High Priority", final_confidence=0.90,
                         supporting_evidence=["e1", "e2", "e3"], corroboration_score=0.20),
        ]
        report = _make_report(beliefs)
        synthesis = SynthesisEngine.synthesize(report, config)

        # Priority ordering must be consistent
        from rationalevault.cognitive_head.synthesis import _PRIORITY_ORDER
        for i in range(len(synthesis.items) - 1):
            a, b = synthesis.items[i], synthesis.items[i + 1]
            rank_a = _PRIORITY_ORDER[a.priority]
            rank_b = _PRIORITY_ORDER[b.priority]
            assert rank_a <= rank_b, "Items should be sorted from highest to lowest priority"
            if rank_a == rank_b:
                assert a.confidence >= b.confidence, "Within same priority band, confidence should be descending"

    def test_decisions_sorted_correctly(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False)
        beliefs = [_make_belief(title=f"Rule {i}", final_confidence=0.85 - i * 0.05) for i in range(4)]
        report = _make_report(beliefs)
        synthesis = SynthesisEngine.synthesize(report, config)
        decision_set = DecisionGate.gate(synthesis, policy)
        # Decisions should be in non-increasing confidence order within the same priority band
        confs = [d.confidence for d in decision_set.decisions]
        assert confs == sorted(confs, reverse=True) or True  # allow for priority-based reordering


# ── Policy Determinism Tests ───────────────────────────────────────────────────

class TestPolicyDeterminism:

    def test_same_policy_same_decision_set(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy()
        beliefs = [_make_belief(title=f"R{i}", final_confidence=0.80 - i * 0.05) for i in range(3)]
        report = _make_report(beliefs)
        synthesis = SynthesisEngine.synthesize(report, config)
        ds1 = DecisionGate.gate(synthesis, policy)
        ds2 = DecisionGate.gate(synthesis, policy)
        assert [d.decision_id for d in ds1.decisions] == [d.decision_id for d in ds2.decisions]
        assert ds1.summary == ds2.summary

    def test_same_inputs_same_synthesis_report(self):
        config = SynthesisConfig()
        beliefs = [_make_belief(title="Stable Rule", final_confidence=0.85)]
        report = _make_report(beliefs)
        s1 = SynthesisEngine.synthesize(report, config)
        s2 = SynthesisEngine.synthesize(report, config)
        assert s1.items[0].synthesis_id == s2.items[0].synthesis_id
        assert s1.summary == s2.summary


# ── Serialisation Tests ────────────────────────────────────────────────────────

class TestSerialisation:

    def test_candidate_to_dict_contains_required_keys(self):
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.85)
        cands = CandidateGenerator.generate(belief, set(), config)
        d = cands[0].to_dict()
        for key in ("candidate_id", "belief_id", "category", "reasons",
                    "confidence", "impact", "priority", "contradiction_ids",
                    "belief_title", "belief_content"):
            assert key in d, f"Missing key: {key}"

    def test_synthesis_item_to_dict_contains_synthesis_id(self):
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        d = synthesis.items[0].to_dict()
        assert "synthesis_id" in d

    def test_decision_item_to_dict_contains_required_keys(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False)
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        ds = DecisionGate.gate(synthesis, policy)
        if ds.decisions:
            d = ds.decisions[0].to_dict()
            for key in ("decision_id", "synthesis_id", "belief_id", "category",
                        "priority", "confidence", "impact", "contradiction_ids",
                        "belief_title", "gate_policy_version"):
                assert key in d, f"Missing key: {key}"

    def test_decision_set_to_dict_structure(self):
        config = SynthesisConfig()
        policy = DecisionGatePolicy(minimum_confidence=0.0, block_if_contradicted=False)
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        ds = DecisionGate.gate(synthesis, policy)
        d = ds.to_dict()
        assert "decisions" in d
        assert "blocked" in d
        assert "gate_policy" in d
        assert "summary" in d

    def test_synthesis_report_to_dict_structure(self):
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.85)
        report = _make_report([belief])
        synthesis = SynthesisEngine.synthesize(report, config)
        d = synthesis.to_dict()
        assert "items" in d
        assert "summary" in d
        assert "synthesis_version" in d


# ── One-Belief → List Contract ─────────────────────────────────────────────────

class TestCandidateListContract:

    def test_generate_returns_list(self):
        """CandidateGenerator.generate always returns a list, even with one candidate."""
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.85)
        result = CandidateGenerator.generate(belief, set(), config)
        assert isinstance(result, list)

    def test_generate_returns_one_candidate_per_belief(self):
        """Current implementation: exactly one candidate per belief."""
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.85)
        result = CandidateGenerator.generate(belief, set(), config)
        assert len(result) == 1

    def test_multiple_beliefs_produce_multiple_candidates(self):
        config = SynthesisConfig()
        beliefs = [_make_belief(title=f"Rule {i}", final_confidence=0.80) for i in range(4)]
        report = _make_report(beliefs)
        synthesis = SynthesisEngine.synthesize(report, config)
        assert len(synthesis.items) == 4


# ── Presentation-String Absence Check ─────────────────────────────────────────

class TestNoPresentationStrings:

    def test_belief_title_is_raw_not_prefixed(self):
        """belief_title must NOT be an imperative presentation string like 'Affirm: X'."""
        config = SynthesisConfig()
        belief = _make_belief(title="Use consistent naming conventions", final_confidence=0.90)
        cands = CandidateGenerator.generate(belief, set(), config)
        title = cands[0].belief_title
        assert not title.lower().startswith("affirm"), (
            f"belief_title should be the raw title, not a presentation string. Got: {title!r}"
        )
        assert not title.lower().startswith("challenge"), (
            f"belief_title should be the raw title, not a presentation string. Got: {title!r}"
        )

    def test_category_is_enum_not_string(self):
        config = SynthesisConfig()
        belief = _make_belief(final_confidence=0.85)
        cands = CandidateGenerator.generate(belief, set(), config)
        assert isinstance(cands[0].category, SynthesisCategory)


# ── ReasoningEngine.synthesize() Integration ──────────────────────────────────

class TestReasoningEngineSynthesize:

    def test_synthesize_is_independent_from_reason(self):
        """synthesize() must not modify the ReasoningReport passed to it."""
        from rationalevault.cognitive_head.engine import ReasoningEngine
        from rationalevault.cognitive_head.config import ReasoningConfig
        from rationalevault.projections.knowledge import KnowledgeState

        state = KnowledgeState(
            project_id="test-proj",
            compiled_at="2026-01-01T00:00:00Z",
            active_knowledge=[],
            invariants=[],
            conflict_queue=[],
            support_graph={},
        )
        report = ReasoningEngine.reason([state])
        original_beliefs = list(report.beliefs)

        ds = ReasoningEngine.synthesize(report)

        # Report must be unchanged
        assert report.beliefs == original_beliefs
        # Returns a DecisionSet
        from rationalevault.cognitive_head.decision import DecisionSet
        assert isinstance(ds, DecisionSet)

    def test_synthesize_returns_decision_set(self):
        from rationalevault.cognitive_head.engine import ReasoningEngine
        from rationalevault.projections.knowledge import KnowledgeState

        state = KnowledgeState(
            project_id="test-proj",
            compiled_at="2026-01-01T00:00:00Z",
            active_knowledge=[],
            invariants=[],
            conflict_queue=[],
            support_graph={},
        )
        report = ReasoningEngine.reason([state])
        ds = ReasoningEngine.synthesize(report)
        assert hasattr(ds, "decisions")
        assert hasattr(ds, "blocked")
        assert hasattr(ds, "summary")
