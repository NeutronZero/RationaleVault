"""Governance Projection implementation conforming to the Projection protocol."""

from __future__ import annotations

from typing import Any, Optional

from rationalevault.projection_platform.models import (
    DependencyKind,
    EventSelector,
    ProjectionCapabilities,
    ProjectionDependency,
    ProjectionHealth,
    ProjectionMetadata,
)
from rationalevault.governance.state import (
    GovernanceAction,
    GovernanceCondition,
    GovernanceRule,
    GovernanceRuleMetadata,
    GovernanceSeverity,
    GovernanceState,
)
from rationalevault.schema.events import EventRecord, EventType


class GovernanceProjection:
    """Governance projection (Archetype: Evaluation).

    Tracks policy configuration and state stored in events.
    Replay stores policy. Runtime applies policy.
    """

    VERSION = 1
    SCHEMA_VERSION = 1

    def __init__(self) -> None:
        self._health = ProjectionHealth.UNKNOWN
        self._ctx: Any = None

    @property
    def metadata(self) -> ProjectionMetadata:
        return ProjectionMetadata(
            id="governance",
            version=self.VERSION,
            schema_version=self.SCHEMA_VERSION,
            consumed_events=EventSelector(
                types=frozenset({
                    EventType.GOVERNANCE_RULE_CREATED,
                    EventType.GOVERNANCE_RULE_UPDATED,
                    EventType.GOVERNANCE_RULE_DELETED,
                })
            ),
            capabilities=ProjectionCapabilities(
                searchable=True,
                snapshotable=True,
                observable=True,
                exportable=True,
                mutable=False,
            ),
            dependencies=(
                ProjectionDependency(
                    projection_id="recommendation",
                    kind=DependencyKind.STATE,
                ),
            ),
            description="Policy evaluation projection producing warnings and decisions",
        )

    def initialize(self, ctx: Any) -> None:
        self._ctx = ctx
        self._health = ProjectionHealth.INITIALIZING

    def reduce(
        self,
        events: list[EventRecord],
        initial_state: Optional[GovernanceState] = None,
    ) -> GovernanceState:
        state = (
            initial_state
            if initial_state is not None
            else GovernanceState(rules=[], sequence=0)
        )

        self._health = ProjectionHealth.BUILDING

        rules_by_key = {(r.metadata.id, r.metadata.version): r for r in state.rules}

        for event in events:
            payload = event.payload
            if event.event_type == EventType.GOVERNANCE_RULE_CREATED:
                rule = self._parse_rule(payload)
                rules_by_key[(rule.metadata.id, rule.metadata.version)] = rule
            elif event.event_type == EventType.GOVERNANCE_RULE_UPDATED:
                rule = self._parse_rule(payload)
                rules_by_key[(rule.metadata.id, rule.metadata.version)] = rule
            elif event.event_type == EventType.GOVERNANCE_RULE_DELETED:
                rule_id = payload.get("rule_id")
                version = payload.get("version", 1)
                if rule_id:
                    rules_by_key.pop((rule_id, version), None)

            state.sequence = max(state.sequence, event.event_sequence)

        # Keep rules sorted deterministically by (id, version)
        sorted_keys = sorted(rules_by_key.keys())
        state.rules = [rules_by_key[k] for k in sorted_keys]

        self._health = ProjectionHealth.READY
        return state

    def _parse_rule(self, payload: dict) -> GovernanceRule:
        from rationalevault.recommendation.state import RecommendationCategory
        meta_payload = payload.get("metadata", {})
        cond_payload = payload.get("condition", {})

        categories = cond_payload.get("categories")
        if categories is not None:
            categories = {RecommendationCategory(c) for c in categories}

        severities = cond_payload.get("severities")
        if severities is not None:
            severities = {GovernanceSeverity(s) for s in severities}

        metadata = GovernanceRuleMetadata(
            id=meta_payload["id"],
            version=meta_payload.get("version", 1),
            description=meta_payload.get("description", ""),
            severity=GovernanceSeverity(meta_payload.get("severity", "warning")),
            action=GovernanceAction(meta_payload.get("action", "notify")),
        )
        condition = GovernanceCondition(
            categories=categories,
            minimum_priority=cond_payload.get("minimum_priority"),
            severities=severities,
        )
        return GovernanceRule(
            metadata=metadata,
            condition=condition,
            enabled=payload.get("enabled", True),
        )

    def serialize(self, state: GovernanceState) -> dict:
        return {
            "rules": [
                {
                    "metadata": {
                        "id": r.metadata.id,
                        "version": r.metadata.version,
                        "description": r.metadata.description,
                        "severity": r.metadata.severity.value,
                        "action": r.metadata.action.value,
                    },
                    "condition": {
                        "categories": (
                            [c.value for c in r.condition.categories]
                            if r.condition.categories is not None
                            else None
                        ),
                        "minimum_priority": r.condition.minimum_priority,
                        "severities": (
                            [s.value for s in r.condition.severities]
                            if r.condition.severities is not None
                            else None
                        ),
                    },
                    "enabled": r.enabled,
                }
                for r in state.rules
            ],
            "sequence": state.sequence,
            "schema_version": self.SCHEMA_VERSION,
        }

    def deserialize(self, payload: dict) -> GovernanceState:
        from rationalevault.recommendation.state import RecommendationCategory

        rules = []
        for r in payload.get("rules", []):
            meta = r["metadata"]
            cond = r["condition"]

            categories = cond.get("categories")
            if categories is not None:
                categories = {RecommendationCategory(c) for c in categories}

            severities = cond.get("severities")
            if severities is not None:
                severities = {GovernanceSeverity(s) for s in severities}

            metadata = GovernanceRuleMetadata(
                id=meta["id"],
                version=meta["version"],
                description=meta["description"],
                severity=GovernanceSeverity(meta["severity"]),
                action=GovernanceAction(meta["action"]),
            )
            condition = GovernanceCondition(
                categories=categories,
                minimum_priority=cond.get("minimum_priority"),
                severities=severities,
            )
            rules.append(
                GovernanceRule(
                    metadata=metadata,
                    condition=condition,
                    enabled=r.get("enabled", True),
                )
            )

        # Keep sorted
        rules.sort(key=lambda r: (r.metadata.id, r.metadata.version))

        return GovernanceState(
            rules=rules,
            sequence=payload.get("sequence", 0),
        )

    def health(self) -> ProjectionHealth:
        return self._health

    def shutdown(self) -> None:
        self._health = ProjectionHealth.SHUTDOWN
        self._ctx = None
