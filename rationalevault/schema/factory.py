from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath
from rationalevault.schema.events import EventType
from rationalevault.projections.governance import GovernanceState

class SchemaPolicyFactory:
    """Compiles SchemaPolicy from GovernanceState.

    Does NOT own UpcasterRegistry. Only compiles metadata.
    Does NOT modify GovernanceState — reads it, compiles, returns new object.
    """

    def compile(self, governance_state: GovernanceState) -> SchemaPolicy:
        """Build SchemaPolicy from current governance state."""
        schemas = {}
        for event_type_str, (version, _eff_seq) in governance_state.schema_versions.items():
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                continue
            schemas[event_type] = EventSchema(
                event_type=event_type,
                latest_version=version,
                migration_path=MigrationPath(),
            )
        return SchemaPolicy(_schemas=schemas)

    def compile_at_sequence(self, governance_state: GovernanceState, sequence: int) -> SchemaPolicy:
        """Build SchemaPolicy as of a specific ledger sequence."""
        schemas = {}
        for event_type_str, (version, eff_seq) in governance_state.schema_versions.items():
            if eff_seq <= sequence:
                try:
                    event_type = EventType(event_type_str)
                except ValueError:
                    continue
                schemas[event_type] = EventSchema(
                    event_type=event_type,
                    latest_version=version,
                    migration_path=MigrationPath(),
                )
        return SchemaPolicy(_schemas=schemas)