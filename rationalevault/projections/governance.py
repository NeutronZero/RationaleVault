import logging
from dataclasses import dataclass, field
from typing import ClassVar, Any, Optional

from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.schema.events import EventRecord, GovernanceRecord, GovernanceDomain, GovernanceAction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolicyValue:
    value: Any
    effective_sequence: int


@dataclass(frozen=True)
class GovernanceState:
    """
    State representing the active governance configuration of the platform
    projected from the historical governance event ledger.
    """
    # Maps target name -> PolicyValue(value, effective_sequence)
    policies: dict[str, PolicyValue] = field(default_factory=dict)
    projection_topology: str = "default"
    topology_effective_sequence: int = 0
    # Maps target name -> schema_version, effective_sequence
    schema_versions: dict[str, tuple[int, int]] = field(default_factory=dict)
    # Maps target name -> effective_sequence
    disabled_components: dict[str, int] = field(default_factory=dict)

    def get_effective_policy(self, name: str, sequence: Optional[int] = None) -> Any | None:
        """Retrieve the policy value that was effective at the given sequence number."""
        policy = self.policies.get(name)
        if not policy:
            return None
        if sequence is not None and policy.effective_sequence > sequence:
            return None
        return policy.value

    def get_effective_schema_version(self, event_type: str, sequence: Optional[int] = None) -> int:
        """Retrieve the schema version of an event type effective at the given sequence number."""
        schema = self.schema_versions.get(event_type)
        if not schema:
            return 1  # Default fallback
        ver, eff_seq = schema
        if sequence is not None and eff_seq > sequence:
            return 1
        return ver

    def is_component_disabled(self, name: str, sequence: Optional[int] = None) -> bool:
        """Check if a component was disabled at the given sequence number."""
        disabled_seq = self.disabled_components.get(name)
        if disabled_seq is None:
            return False
        if sequence is not None and disabled_seq > sequence:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "policies": {k: {"value": v.value, "seq": v.effective_sequence} for k, v in self.policies.items()},
            "projection_topology": self.projection_topology,
            "topology_effective_sequence": self.topology_effective_sequence,
            "schema_versions": {k: {"ver": v[0], "seq": v[1]} for k, v in self.schema_versions.items()},
            "disabled_components": self.disabled_components,
        }


class GovernanceProjection(BaseProjection):
    """
    GovernanceProjection projects the current system/interpretation configuration
    from the stream of GOVERNANCE_DECISION_RECORDED events.
    """
    projection_name: ClassVar[str] = "Governance"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
    dependencies: ClassVar[list[type[BaseProjection]]] = []
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 1

    @staticmethod
    def project(events: list[EventRecord]) -> GovernanceState:
        policies: dict[str, PolicyValue] = {}
        projection_topology = "default"
        topology_effective_sequence = 0
        schema_versions: dict[str, tuple[int, int]] = {}
        disabled_components: dict[str, int] = {}

        # Sort events by sequence to enforce deterministic latest-wins ordering
        sorted_events = sorted(events, key=lambda e: e.event_sequence)

        for event in sorted_events:
            et_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
            if et_str != "GOVERNANCE_DECISION_RECORDED":
                continue

            try:
                record = GovernanceRecord.from_dict(event.payload)
            except Exception as ex:
                logger.error(f"Failed to parse GovernanceRecord from event {event.id}: {ex}")
                continue

            # Fallback to event's sequence if effective_sequence is unspecified or 0
            effective_seq = record.effective_sequence or event.event_sequence
            domain = record.domain
            action = record.action

            if domain == GovernanceDomain.POLICY:
                if action == GovernanceAction.ADJUSTED:
                    policies[record.target] = PolicyValue(record.new_version, effective_seq)
                elif action == GovernanceAction.DISABLED:
                    policies.pop(record.target, None)

            elif domain == GovernanceDomain.PROJECTION:
                if action == GovernanceAction.TOPOLOGY_CHANGED:
                    projection_topology = record.target
                    topology_effective_sequence = effective_seq
                elif action == GovernanceAction.DISABLED:
                    disabled_components[record.target] = effective_seq
                elif action == GovernanceAction.ADJUSTED:  # re-enabled
                    disabled_components.pop(record.target, None)

            elif domain == GovernanceDomain.SCHEMA:
                if action == GovernanceAction.MIGRATION_APPLIED:
                    if record.new_version:
                        schema_versions[record.target] = (int(record.new_version), effective_seq)

        return GovernanceState(
            policies=policies,
            projection_topology=projection_topology,
            topology_effective_sequence=topology_effective_sequence,
            schema_versions=schema_versions,
            disabled_components=disabled_components,
        )
