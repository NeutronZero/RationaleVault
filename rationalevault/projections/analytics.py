"""
RationaleVault Skill Platform — Execution Analytics Projection.

Computes Layer 1 aggregated statistics (skills, plugins, durations, costs, promotions)
from raw execution events.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import ClassVar

from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.schema.events import EventRecord, EventType
from rationalevault.skill_platform.execution_state import ExecutionStateProjection, ExecutionEntry
from rationalevault.skill_platform.intelligence_models import (
    ExecutionAnalytics,
    ExecutionAnalyticsConfig,
    ExecutionAnalyticsState,
    SkillExecutionStatistics,
    PluginExecutionStatistics,
    ExecutionDurationStatistics,
    ArtifactPromotionStatistics,
    CostBreakdown,
    ExecutionCostReport,
)


class ExecutionAnalyticsProjection(BaseProjection):
    """
    ExecutionAnalyticsProjection computes statistics over execution records.
    """
    projection_name: ClassVar[str] = "execution_analytics"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
    dependencies: ClassVar[list[type[BaseProjection]]] = [ExecutionStateProjection]
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 95

    @staticmethod
    def project(
        events: list[EventRecord],
        config: ExecutionAnalyticsConfig = ExecutionAnalyticsConfig(),
        known_decision_ids: list[str] | None = None,
    ) -> ExecutionAnalyticsState:
        # 1. Build base ExecutionState
        state = ExecutionStateProjection.build(events, known_decision_ids)

        # Build skill-to-plugin mapping dynamically from PluginRegistry
        from rationalevault.skill_platform.plugin import PluginRegistry
        skill_to_plugin = {}
        for desc in PluginRegistry.get_all_descriptors():
            inst = PluginRegistry.get_instance(desc.plugin_id)
            if inst:
                try:
                    for m in inst.manifests():
                        skill_to_plugin[m.skill_id] = desc.plugin_id
                        skill_to_plugin[m.name] = desc.plugin_id
                except Exception:
                    pass

        # 2. Compute Skill Execution Statistics
        skills_stats = {}
        for skill_id, total in state.execution_counts.items():
            success = state.success_counts.get(skill_id, 0)
            success_rate = success / total if total > 0 else 0.0

            # Gather all executions for this skill
            all_entries: list[ExecutionEntry] = []
            for e in state.completed_executions + state.failed_executions + state.timeout_executions + state.denied_executions:
                if e.skill_id == skill_id:
                    all_entries.append(e)

            # Sort chronologically by started_at (handling None safely)
            all_entries.sort(key=lambda x: x.started_at or "")

            # Rolling window success rate
            window = all_entries[-config.window_size:] if total > 0 else []
            rolling_total = len(window)
            rolling_success = sum(1 for e in window if e.state == "COMPLETED")
            rolling_success_rate = rolling_success / rolling_total if rolling_total > 0 else 0.0

            # Count timeouts and schema failures
            timeouts = sum(1 for e in all_entries if e.state == "TIMEOUT")
            schema_failures = sum(
                1 for e in all_entries if e.error and "validation failed" in e.error.lower()
            )

            skills_stats[skill_id] = SkillExecutionStatistics(
                skill_id=skill_id,
                total_executions=total,
                success_rate=success_rate,
                rolling_success_rate=rolling_success_rate,
                timeouts=timeouts,
                schema_failures=schema_failures,
            )

        # 3. Compute Plugin Execution Statistics
        plugin_counts: dict[str, int] = {}
        plugin_failures: dict[str, int] = {}
        plugin_timeouts: dict[str, int] = {}
        plugin_denials: dict[str, int] = {}

        for e in state.completed_executions + state.failed_executions + state.timeout_executions + state.denied_executions:
            # Map skill_id/name to plugin_id if registered
            pid = skill_to_plugin.get(e.skill_id)
            if not pid:
                # Fallback check metadata in event payload directly if available
                # e.g., if target.metadata has plugin_id, the executor includes it
                pass
            
            if pid:
                plugin_counts[pid] = plugin_counts.get(pid, 0) + 1
                if e.state == "FAILED":
                    plugin_failures[pid] = plugin_failures.get(pid, 0) + 1
                elif e.state == "TIMEOUT":
                    plugin_timeouts[pid] = plugin_timeouts.get(pid, 0) + 1
                elif e.state == "DENIED":
                    plugin_denials[pid] = plugin_denials.get(pid, 0) + 1

        plugins_stats = {}
        for pid in plugin_counts:
            plugins_stats[pid] = PluginExecutionStatistics(
                plugin_id=pid,
                total_executions=plugin_counts[pid],
                failures=plugin_failures.get(pid, 0),
                timeouts=plugin_timeouts.get(pid, 0),
                denials=plugin_denials.get(pid, 0),
            )

        # 4. Compute Durations
        durations_stats = {}
        for skill_id, ds in state.durations.items():
            if ds:
                durations_stats[skill_id] = ExecutionDurationStatistics(
                    skill_id=skill_id,
                    mean_duration_ms=sum(ds) / len(ds),
                    min_duration_ms=min(ds),
                    max_duration_ms=max(ds),
                )

        # 5. Compute Artifact Promotion Statistics
        # We parse the SKILL_EXECUTED events to find the gate results and artifact promotions.
        cand_count = 0
        prom_count = 0
        rej_count = 0
        gate_scores = []
        violations = {}
        artifact_sizes = []

        for event in events:
            if event.event_type != EventType.SKILL_EXECUTED:
                continue
            payload = event.payload
            
            # Check for gate result or promotion metadata inside execution events
            # Let's inspect where initial result is logged or if promotion_report is serialized in payload.
            # In executor.py: to_event_payload() returns payload containing `output_hash`.
            # Let's also check if there is custom gate evaluation recorded.
            # During test execution, results are captured. If promotion report exists in payload:
            report_dict = payload.get("promotion_report") or {}
            promoted_list = report_dict.get("promoted", [])
            rejected_list = report_dict.get("rejected", [])
            gate_res_dict = report_dict.get("gate_result", {})
            eval_dict = report_dict.get("evaluation", {})

            # Count candidates
            cand_count += len(promoted_list) + len(rejected_list)
            prom_count += len(promoted_list)
            rej_count += len(rejected_list)

            # Record gate scores
            if "score" in eval_dict:
                gate_scores.append(eval_dict["score"])

            # Record violations
            for violation in gate_res_dict.get("violations", []):
                violations[violation] = violations.get(violation, 0) + 1

            # Record artifact sizes
            for art in promoted_list:
                if "size" in art:
                    artifact_sizes.append(art["size"])

        avg_gate_score = sum(gate_scores) / len(gate_scores) if gate_scores else 0.0
        most_common_violation = max(violations, key=violations.get) if violations else None
        avg_art_size = sum(artifact_sizes) / len(artifact_sizes) if artifact_sizes else 0.0

        promotions = ArtifactPromotionStatistics(
            candidate_count=cand_count,
            promoted_count=prom_count,
            rejected_count=rej_count,
            average_gate_score=avg_gate_score,
            most_common_violation=most_common_violation,
            average_artifact_size=avg_art_size,
        )

        # 6. Cost allocation
        # We calculate estimated compute costs from execution durations.
        cost_reports = []
        for e in state.completed_executions + state.failed_executions + state.timeout_executions + state.denied_executions:
            dur_ms = e.duration_ms or 0
            # Simple version 1.0 linear cost model: duration * duration_weight
            dur_weight = 0.0001
            mem_weight = 0.0
            cpu_weight = 0.0
            total_cost = dur_ms * dur_weight

            breakdown = CostBreakdown(
                duration_weight=dur_weight,
                memory_weight=mem_weight,
                cpu_weight=cpu_weight,
                total_cost=total_cost,
            )
            cost_reports.append(
                ExecutionCostReport(
                    duration_ms=dur_ms,
                    cpu_time_ms=None,
                    memory_bytes=None,
                    cost_model_version=config.cost_model_version,
                    cost_components=breakdown,
                )
            )

        analytics = ExecutionAnalytics(
            skills=skills_stats,
            plugins=plugins_stats,
            durations=durations_stats,
            promotions=promotions,
            costs=cost_reports,
        )

        analytics_hash = analytics.compute_hash()
        
        # Calculate projection_hash
        raw_repr = f"analytics:{analytics_hash}:{config.window_size}"
        projection_hash = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()[:16].upper()

        # Input snapshot hash
        input_hash = hashlib.sha256(
            "".join(e.execution_id for e in state.completed_executions).encode("utf-8")
        ).hexdigest()[:16].upper()

        compiled_at = datetime.now(timezone.utc).isoformat()

        return ExecutionAnalyticsState(
            version="1.0.0",
            compiled_at=compiled_at,
            analytics=analytics,
            analytics_hash=analytics_hash,
            projection_hash=projection_hash,
            input_snapshot_hash=input_hash,
        )
