"""CLI handler for `rv governance` subcommands."""

from __future__ import annotations
from rationalevault.logging import get_logger

logger = get_logger(__name__)



import argparse
import sys


def cmd_governance(args: argparse.Namespace) -> None:
    """Handle `rv governance` subcommands."""
    if args.governance_command == "show":
        _cmd_governance_show(args)
    else:
        logger.error(f"Unknown governance command '{args.governance_command}'")
        sys.exit(1)


def _cmd_governance_show(args: argparse.Namespace) -> None:
    """Show governance warnings."""
    from datetime import datetime

    from rationalevault.governance.projection import GovernanceProjection
    from rationalevault.governance.runtime import (
        GovernanceRuntime,
        DefaultEvidenceProvider,
    )
    from rationalevault.governance.state import (
        GovernanceState,
        GovernanceSeverity,
        GovernanceAction,
    )
    from rationalevault.projection_platform.context import DependencyReader
    from rationalevault.recommendation.projection import (
        RecommendationProjection,
    )

    from rationalevault.projection_platform.manager import ProjectionManager
    from rationalevault.projection_platform.registry import ProjectionRegistry
    from rationalevault.projection_platform.compiler import ProjectionCompiler

    runtime = GovernanceRuntime()
    state = None
    rec_state = None

    from rationalevault.cli.utils.project import _resolve_project_id
    project_id = _resolve_project_id()

    # If project_id is not the zero UUID (which means no project)
    from uuid import UUID
    zero_uuid = UUID("00000000-0000-0000-0000-000000000000")
    if project_id and project_id != zero_uuid:
        # Setup compiler & registry with default deps
        registry = ProjectionRegistry()
        registry.register(GovernanceProjection())
        registry.register(RecommendationProjection())
        
        # TODO: Remove DummyProjection adapter once KnowledgeProjection and EmbeddingProjection
        # are first-class ProjectionPlatform projections. This is a temporary bridge to satisfy
        # ProjectionCompiler dependency resolution until they are fully migrated.
        from rationalevault.projection_platform.protocols import Projection
        from rationalevault.projection_platform.models import ProjectionMetadata, ProjectionHealth, ProjectionCapabilities, EventSelector
        
        class DummyProjection(Projection):
            def __init__(self, id: str):
                self._id = id
            @property
            def metadata(self) -> ProjectionMetadata:
                return ProjectionMetadata(id=self._id, version=1, description="Dummy", schema_version=1, consumed_events=EventSelector(types=frozenset()), capabilities=ProjectionCapabilities())
            def initialize(self, ctx) -> None: pass
            def reduce(self, events, initial_state=None): return None
            def serialize(self, state): return {}
            def deserialize(self, payload): return None
            def health(self) -> ProjectionHealth: return ProjectionHealth.READY
            def shutdown(self) -> None: pass

        registry.register(DummyProjection("knowledge"))
        registry.register(DummyProjection("embedding"))
        
        compiler = ProjectionCompiler(registry=registry)
        manager = ProjectionManager(registry, compiler)
        
        try:
            state = manager.get_projection_state(project_id, "governance")
            rec_state = manager.get_projection_state(project_id, "recommendation")
        except Exception:
            pass

    if state is None:
        state = GovernanceState()
        project_id = None # Force ephemeral mode if we failed to get state

    if rec_state is None:
        from rationalevault.recommendation.state import RecommendationState
        rec_state = RecommendationState()

    # If no rules exist, register a default warning rule to demonstrate ONLY in ephemeral mode
    if not project_id and not state.rules:
        from rationalevault.governance.state import (
            GovernanceRule,
            GovernanceRuleMetadata,
            GovernanceCondition,
        )
        from rationalevault.recommendation.state import RecommendationCategory
        default_rule = GovernanceRule(
            metadata=GovernanceRuleMetadata(
                id="default_risk_notify",
                version=1,
                description="Default policy to notify about risks",
                severity=GovernanceSeverity.WARNING,
                action=GovernanceAction.NOTIFY,
            ),
            condition=GovernanceCondition(
                categories={RecommendationCategory.RISK},
                minimum_priority=0.4,
            ),
        )
        state.rules.append(default_rule)
    elif project_id and not state.rules:
        # We are in a project, and the policy is explicitly empty.
        # We will output empty results.
        pass


    reader = DependencyReader()
    reader.set("recommendation", rec_state)
    provider = DefaultEvidenceProvider(reader)

    evals = runtime.evaluate_rules(state, provider)
    warnings = runtime.generate_warnings(state, evals, query_time=datetime.now())

    # Apply severity/action filters
    sev_filter = getattr(args, "severity", None)
    act_filter = getattr(args, "action", None)

    sev = None
    if sev_filter:
        try:
            sev = GovernanceSeverity(sev_filter)
        except ValueError:
            logger.error(f"Unknown severity '{sev_filter}'")
            sys.exit(1)

    act = None
    if act_filter:
        try:
            act = GovernanceAction(act_filter)
        except ValueError:
            logger.error(f"Unknown action '{act_filter}'")
            sys.exit(1)

    limit = getattr(args, "limit", 50)
    results = runtime.search(warnings, severity=sev, action=act, limit=limit)

    fmt = getattr(args, "format", "table")
    if fmt == "json":
        import json
        output = [
            {
                "id": w.id,
                "rule_id": w.rule_id,
                "rule_version": w.rule_version,
                "target_entity": w.target_entity,
                "severity": w.severity.value,
                "action": w.action.value,
                "message": w.message,
                "evidence": w.evidence,
                "created_at": w.created_at.isoformat(),
            }
            for w in results
        ]
        print(json.dumps(output, indent=2))
    else:
        if not results:
            if project_id and not state.rules:
                print("No governance rules configured. Define rules via GOVERNANCE_RULE_CREATED events.")
            else:
                print("No governance warnings found.")
            return

        print(f"Governance Warnings ({len(results)} of {len(warnings)})")
        print("=" * 80)

        for w in results:
            sev_str = w.severity.value.upper()
            act_str = w.action.value.upper()
            print(
                f"  [{sev_str:<8}] [{act_str:<8}] "
                f"target={w.target_entity:<12} | {w.message}"
            )
            print(f"    rule={w.rule_id} v{w.rule_version} | evidence={w.evidence}")

        print("=" * 80)
