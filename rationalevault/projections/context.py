from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from rationalevault.schema.policy import SchemaPolicy
from rationalevault.projections.governance import GovernanceState


class ReplayMode(str, Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    INTERPRETIVE = "INTERPRETIVE"
    COUNTERFACTUAL = "COUNTERFACTUAL"


@dataclass(frozen=True)
class ReplayContext:
    """Session parameters for replay execution.

    Contains NO schema version logic.
    Contains NO resolver — that belongs in ReplayPipeline.
    SchemaPolicy is the single source of truth for schema decisions.
    """
    max_sequence: Optional[int] = None
    schema_policy: SchemaPolicy = field(default_factory=lambda: SchemaPolicy(_schemas={}))


@dataclass(frozen=True)
class ReplayRequest:
    """
    Declarative user request specifying how a replay operation should be conducted.
    """
    mode: ReplayMode = ReplayMode.CURRENT
    sequence: Optional[int] = None


@dataclass(frozen=True)
class InterpretiveContext:
    """
    Semantic interpretation context representing active governance rules 
    and target execution parameters.
    """
    governance: GovernanceState
    replay_mode: ReplayMode
    sequence: Optional[int]
    replay_context: ReplayContext

    def to_replay_context(self) -> ReplayContext:
        """Explicitly converts the interpretive context to a concrete execution context."""
        return self.replay_context


class InterpretiveContextBuilder:
    """
    Assembles an InterpretiveContext from GovernanceState and a ReplayRequest.
    """

    @staticmethod
    def build(
        governance: GovernanceState,
        request: ReplayRequest,
    ) -> InterpretiveContext:
        if request.mode == ReplayMode.COUNTERFACTUAL:
            raise NotImplementedError("Counterfactual replay mode is not supported in the current epoch.")

        from rationalevault.schema.factory import SchemaPolicyFactory

        factory = SchemaPolicyFactory()
        policy = factory.compile(governance)

        max_seq = request.sequence

        if request.mode == ReplayMode.CURRENT:
            max_seq = None

        replay_context = ReplayContext(
            max_sequence=max_seq,
            schema_policy=policy,
        )

        return InterpretiveContext(
            governance=governance,
            replay_mode=request.mode,
            sequence=max_seq,
            replay_context=replay_context,
        )
