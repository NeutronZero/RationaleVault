from __future__ import annotations

import pytest
import uuid

from rationalevault.projections.governance import GovernanceState, PolicyValue
from rationalevault.projections.context import ReplayMode, ReplayRequest, InterpretiveContext, InterpretiveContextBuilder
from rationalevault.schema.policy import SchemaPolicy


def test_interpretive_context_builder_builds_correctly() -> None:
    gov = GovernanceState(
        policies={"max_retries": PolicyValue("3", 10)},
        projection_topology="custom_topology",
        topology_effective_sequence=15,
    )

    request = ReplayRequest(
        mode=ReplayMode.HISTORICAL,
        sequence=50,
    )

    ctx = InterpretiveContextBuilder.build(
        governance=gov,
        request=request,
    )

    assert isinstance(ctx, InterpretiveContext)
    assert ctx.replay_mode == ReplayMode.HISTORICAL
    assert ctx.sequence == 50
    assert ctx.to_replay_context().max_sequence == 50
    assert isinstance(ctx.to_replay_context().schema_policy, SchemaPolicy)
    assert ctx.governance is gov
    
    # Check effective configuration at target sequence
    assert ctx.governance.get_effective_policy("max_retries", 50) == "3"
    assert ctx.governance.projection_topology == "custom_topology"


def test_counterfactual_raises_not_implemented() -> None:
    gov = GovernanceState()
    request = ReplayRequest(
        mode=ReplayMode.COUNTERFACTUAL,
    )

    with pytest.raises(NotImplementedError) as exc_info:
        InterpretiveContextBuilder.build(gov, request)

    assert "Counterfactual replay mode is not supported" in str(exc_info.value)


def test_current_mode_ignores_sequence_limit() -> None:
    gov = GovernanceState()
    request = ReplayRequest(
        mode=ReplayMode.CURRENT,
        sequence=42,  # Should be set to None by CURRENT logic
    )

    ctx = InterpretiveContextBuilder.build(gov, request)
    assert ctx.replay_mode == ReplayMode.CURRENT
    assert ctx.sequence is None
    assert ctx.to_replay_context().max_sequence is None
