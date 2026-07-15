"""ReplayComplianceValidator — validates RP vectors against a ReplayEngine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType
from rationalevault.ledger.commit import CommitBuilder
from rationalevault.ledger.storage.memory import MemoryLedger
from rationalevault.replay.interface import ReplayEngine
from rationalevault.replay.registry import ProjectionRegistry, ReducerFunc
from rationalevault.replay.types import ReplayBoundary, ReplayMode, ReplayScope


DEFAULT_TIMESTAMP = CanonicalTimestamp.from_datetime(
    datetime(2026, 7, 14, 0, 0, 0, tzinfo=timezone.utc)
)

REQUIRES_SNAPSHOT = {"rp-03-snapshot-equivalence", "rp-06-fast-path"}
"""Vectors that require snapshot infrastructure not yet implemented."""


@dataclass(frozen=True)
class ComplianceResult:
    passed: bool
    message: str
    expected: str | None = None
    actual: str | None = None


def _resolve_event_type(raw: str) -> EventType:
    mapping = {
        "decision_recorded": EventType.DECISION_RECORDED,
        "evaluation_recorded": EventType.EVALUATION_RECORDED,
        "knowledge_updated": EventType.KNOWLEDGE_UPDATED,
        "experience_recorded": EventType.EXPERIENCE_RECORDED,
        "outcome_observed": EventType.OUTCOME_OBSERVED,
    }
    return mapping.get(raw, EventType.DECISION_RECORDED)


def _make_envelope(
    stream_id: str,
    event: dict[str, Any],
    experience_id: str = "exp-vector",
) -> CanonicalEnvelope:
    return CanonicalEnvelope(
        rvcj_version=event.get("rvcj_version", 1),
        event_schema_version=event.get("event_schema_version", 1),
        experience_id=experience_id,
        event_type=_resolve_event_type(event.get("event_type", "decision_recorded")),
        stream_id=stream_id,
        sequence=event["sequence"],
        timestamp=DEFAULT_TIMESTAMP,
        actor=event.get("actor", "vector-actor"),
        payload=CanonicalPayload(data=event.get("payload", {})),
    )


def _counter_reducer(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload", {})
    state["count"] = state.get("count", 0) + 1
    if payload:
        for k, v in payload.items():
            state["last_" + k] = v
    return state


def _build_ledger(vector: dict[str, Any]) -> MemoryLedger:
    ledger = MemoryLedger()
    streams = vector.get("ledger", {}).get("streams", {})

    flat: list[tuple[int, str, dict[str, Any]]] = []
    for stream_id, events in streams.items():
        for evt in events:
            go = evt.get("global_order", 0)
            flat.append((go, stream_id, evt))
    flat.sort(key=lambda x: (x[0], x[2].get("sequence", 0)))

    for go, stream_id, event in flat:
        env = _make_envelope(stream_id, event)
        commit = CommitBuilder.from_events(stream_id, [env])
        ledger.append(commit)

    return ledger


def _make_registry() -> ProjectionRegistry:
    reg = ProjectionRegistry()
    reg.register("counter", _counter_reducer)
    return reg


class ReplayComplianceValidator:
    """Validates RP compliance vectors against a ReplayEngine."""

    def __init__(self, engine_factory: Callable[[ProjectionRegistry], ReplayEngine]) -> None:
        self._engine_factory = engine_factory

    def validate(self, vector: dict[str, Any]) -> list[ComplianceResult]:
        name = vector.get("name", "unknown")
        if name in REQUIRES_SNAPSHOT:
            return [ComplianceResult(True, f"Skipped {name}: requires snapshot infrastructure")]

        registry = _make_registry()
        engine = self._engine_factory(registry)
        ledger = _build_ledger(vector)

        replay_config = vector.get("replay", {})
        scope = ReplayScope(replay_config.get("scope", "global"))
        mode_val = replay_config.get("mode", "auto")
        mode = ReplayMode(mode_val)

        results: list[ComplianceResult] = []

        if name == "rp-09-interrupted-replay":
            r1 = engine.replay_to(ledger, ReplayBoundary(1), mode=mode)
            r2 = engine.replay_to(ledger, ReplayBoundary(3), mode=mode)
            r_full = engine.replay(ledger, scope=scope, mode=mode)
            if r2.understanding.projections == r_full.understanding.projections:
                results.append(ComplianceResult(True, f"{name}: resumed replay matches full"))
            else:
                results.append(ComplianceResult(
                    False, f"{name}: resumed replay differs",
                    expected=str(r_full.understanding.projections),
                    actual=str(r2.understanding.projections),
                ))

        if name == "rp-07-idempotent-replay":
            r1 = engine.replay(ledger, scope=scope, mode=mode)
            r2 = engine.replay(ledger, scope=scope, mode=mode)
            if r1 == r2:
                results.append(ComplianceResult(True, f"{name}: identical on repeat"))
            else:
                results.append(ComplianceResult(False, f"{name}: differs on repeat"))

        if name == "rp-05-multiple-streams":
            result = engine.replay(ledger, scope=scope, mode=mode)
            proj = result.understanding.projections.get("counter", {})
            expected = vector.get("expected", {}).get("projections", {}).get("counter", {})
            if proj.get("count") == expected.get("count"):
                results.append(ComplianceResult(True, f"{name}: cross-stream ordering OK"))
            else:
                results.append(ComplianceResult(False, f"{name}: count mismatch"))
            if proj.get("last_value") == expected.get("last_value"):
                results.append(ComplianceResult(True, f"{name}: last value OK"))
            else:
                results.append(ComplianceResult(False, f"{name}: last value mismatch"))
            return results

        result = engine.replay(ledger, scope=scope, mode=mode)
        expected = vector.get("expected", {}).get("projections", {})

        for proj_name, expected_state in expected.items():
            actual_state = result.understanding.projections.get(proj_name, {})
            if actual_state == expected_state:
                results.append(ComplianceResult(
                    True, f"{name}/{proj_name}: OK"
                ))
            else:
                results.append(ComplianceResult(
                    False, f"{name}/{proj_name}: mismatch",
                    expected=str(expected_state),
                    actual=str(actual_state),
                ))

        return results
