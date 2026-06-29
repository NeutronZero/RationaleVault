from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from rationalevault.schema.resolver import ReplayResolver
from rationalevault.projections.governance import GovernanceState


class ReplayMode(str, Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    INTERPRETIVE = "INTERPRETIVE"
    COUNTERFACTUAL = "COUNTERFACTUAL"


@dataclass(frozen=True)
class ReplayContext:
    """
    Context parameters for a replay execution session.
    
    Acts as the parameter envelope for controlling schema versions,
    sequence bounds, and other constraints. Owns the ReplayResolver
    to define how the replay is interpreted.
    """
    max_sequence: Optional[int] = None
    target_schema_version: int = 2
    resolver: ReplayResolver = field(default_factory=ReplayResolver)

    def __post_init__(self) -> None:
        if self.resolver.target_schema_version != self.target_schema_version:
            object.__setattr__(
                self,
                "resolver",
                ReplayResolver(self.resolver.registry, self.target_schema_version)
            )


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

        from rationalevault.schema.upcaster import UpcasterRegistry
        from rationalevault.schema.resolver import ReplayResolver

        # 1. Resolve resolver config based on mode and sequence bounds
        registry = UpcasterRegistry.default()
        max_seq = request.sequence

        if request.mode == ReplayMode.CURRENT:
            max_seq = None
            # Current mode uses the latest schema resolvers / registry directly
        
        elif request.mode == ReplayMode.HISTORICAL:
            # Historical mode enforces sequence limits, but uses default unmigrated resolvers
            pass
            
        elif request.mode == ReplayMode.INTERPRETIVE:
            # Interpretive mode configures upcasters effective at request.sequence
            # Note: We query the registry for upcasters matching effective schemas
            # projected by the GovernanceState at request.sequence.
            pass

        resolver = ReplayResolver(registry, target_schema_version=2)

        # 2. Build downstream ReplayContext (execution parameters)
        replay_context = ReplayContext(
            max_sequence=max_seq,
            target_schema_version=2,
            resolver=resolver,
        )

        return InterpretiveContext(
            governance=governance,
            replay_mode=request.mode,
            sequence=max_seq,
            replay_context=replay_context,
        )
