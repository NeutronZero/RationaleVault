from __future__ import annotations
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import ClassVar, Any

from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.schema.events import EventRecord, EventType
from rationalevault.skill_platform.intelligence_models import ExecutionLearningRecord
from rationalevault.skill_platform.reflection_models import (
    ReflectionStatus,
    ReflectionConfig,
    Reflection,
    ReflectionReport,
)
from rationalevault.skill_platform.reflection_engine import (
    ReflectionCandidateBuilder,
    MinSupportingRecordsRule,
    RecurrenceThresholdRule,
    ConflictingEvidenceRule,
    MinConfidenceRule,
    DuplicateSuppressionRule,
    ReflectionRuleEngine,
    ReflectionCompiler,
)
from rationalevault.skill_platform.reflection_events import (
    ReflectionCandidateCreatedPayload,
    ReflectionAssessedPayload,
    ReflectionGeneratedPayload,
    ReflectionTracedPayload,
)


@dataclass(frozen=True)
class ReflectionEventBundle:
    """Collection of event payloads produced during a reflection cycle.

    These are the contracts that get emitted to the Event Ledger.
    The domain ReflectionReport is derived from these events.
    """
    candidate_created: list[ReflectionCandidateCreatedPayload] = field(default_factory=list)
    assessed: list[ReflectionAssessedPayload] = field(default_factory=list)
    generated: list[ReflectionGeneratedPayload] = field(default_factory=list)
    traced: list[ReflectionTracedPayload] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_created": [p.to_dict() for p in self.candidate_created],
            "assessed": [p.to_dict() for p in self.assessed],
            "generated": [p.to_dict() for p in self.generated],
            "traced": [p.to_dict() for p in self.traced],
        }


class ReflectionStateProjection(BaseProjection):
    """
    DERIVED projection processing learning records and historical events to yield a compiled ReflectionReport.

    Event hierarchy:
        REFLECTION_CANDIDATE_CREATED
                ↓
        REFLECTION_ASSESSED
                ↓
        REFLECTION_GENERATED
                ↓
        REFLECTION_TRACED
    """
    projection_name: ClassVar[str] = "reflection_state"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
    dependencies: ClassVar[list[type[BaseProjection]]] = []
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 95

    @classmethod
    def project(
        cls,
        events: list[EventRecord],
        learning_records: list[ExecutionLearningRecord],
        config: ReflectionConfig,
        created_at: str | None = None
    ) -> tuple[ReflectionReport, ReflectionEventBundle]:
        """
        Run the reflection pipeline and produce both:
        1. ReflectionReport (domain object, derived from events)
        2. ReflectionEventBundle (event payloads for ledger emission)
        """
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()

        # Rebuild historical reflections from events (source of truth)
        historical_reflections: list[Reflection] = []
        for event in events:
            if event.event_type == EventType.REFLECTION_GENERATED:
                payload = event.payload
                if "reflection_id" in payload:
                    try:
                        historical_reflections.append(Reflection.from_dict(payload))
                    except Exception:
                        ref_text = payload.get("reflection", "")
                        historical_reflections.append(
                            Reflection(
                                reflection_id=f"REFL-HIST-{event.event_sequence}",
                                candidate_id="RCAND-HISTORICAL",
                                status=ReflectionStatus.COMPLETED,
                                insights=[ref_text],
                                reconstructed_rationale="Loaded from event history",
                                actionable_guidelines=[],
                                created_at=created_at
                            )
                        )

        active_targets = set()
        for ref in historical_reflections:
            if ref.status == ReflectionStatus.ACTIVE or ref.status == ReflectionStatus.COMPLETED:
                if "target '" in ref.reconstructed_rationale:
                    parts = ref.reconstructed_rationale.split("target '")
                    if len(parts) > 1:
                        target = parts[1].split("'")[0]
                        active_targets.add(target)

        # Build candidates (domain objects + event payloads)
        candidates = ReflectionCandidateBuilder.build_candidates(learning_records, config, created_at)
        candidate_payloads = ReflectionCandidateBuilder.build_payloads(candidates, created_at)

        rules = [
            MinSupportingRecordsRule(min_records=2),
            RecurrenceThresholdRule(threshold=2),
            ConflictingEvidenceRule(),
            MinConfidenceRule(),
            DuplicateSuppressionRule(active_targets=active_targets),
        ]
        rule_engine = ReflectionRuleEngine(rules)

        new_reflections: list[Reflection] = []
        assessed_payloads: list[ReflectionAssessedPayload] = []
        generated_payloads: list[ReflectionGeneratedPayload] = []
        traced_payloads: list[ReflectionTracedPayload] = []
        approved_count = 0
        rejected_count = 0

        for candidate in candidates:
            assessment = rule_engine.assess(candidate, config)
            compiled_ref = ReflectionCompiler.compile(assessment, candidate, created_at)
            new_reflections.append(compiled_ref)

            # Produce event payloads (the contracts)
            assessed_payload = assessment.to_payload(created_at)
            assessed_payloads.append(assessed_payload)

            source_lr_ids = candidate.context.get("supporting_record_ids", []) + candidate.context.get("conflicting_record_ids", [])
            generated_payload = ReflectionCompiler.compile_generated_payload(
                compiled_ref, source_lr_ids, created_at
            )
            generated_payloads.append(generated_payload)

            traced_payload = ReflectionCompiler.compile_traced_payload(
                assessment, compiled_ref.reflection_id, candidate, created_at
            )
            traced_payloads.append(traced_payload)

            if assessment.approved:
                approved_count += 1
            else:
                rejected_count += 1

        all_reflections = historical_reflections + [r for r in new_reflections if r.status == ReflectionStatus.COMPLETED]

        summary = {
            "total_historical_reflections": len(historical_reflections),
            "new_candidates_evaluated": len(candidates),
            "new_reflections_approved": approved_count,
            "new_reflections_rejected": rejected_count,
            "active_reflection_targets": list(active_targets),
        }

        report_id = ReflectionReport.generate_report_id(all_reflections, created_at)

        report = ReflectionReport(
            report_id=report_id,
            reflections=all_reflections,
            summary=summary,
            created_at=created_at,
        )

        bundle = ReflectionEventBundle(
            candidate_created=candidate_payloads,
            assessed=assessed_payloads,
            generated=generated_payloads,
            traced=traced_payloads,
        )

        return report, bundle
