"""Projection Law verification functions.

Each function verifies one Projection Law (ADR-027). They are pure
functions: (projection, provider) → bool. They raise AssertionError
with clear messages on failure.
"""
from __future__ import annotations

import json
import tempfile
from typing import Any

from rationalevault.projection_platform.conformance.providers import (
    ProjectionConformanceProvider,
)
from rationalevault.projection_platform.conformance.replay import replay_events
from rationalevault.projection_platform.models import ProjectionHealth
from rationalevault.projection_platform.protocols import Projection


def verify_determinism(
    projection: Projection,
    provider: ProjectionConformanceProvider,
) -> bool:
    """Law 1: Same events → same state. No external state dependencies.

    Verifies:
    - Two replays of the same events produce equal state.
    - Two independent projection instances produce equal state.
    - serialize → deserialize → serialize produces identical JSON.
    """
    events = provider.events()

    # Same instance, two replays
    state1 = replay_events(projection, events, provider)
    state2 = replay_events(projection, events, provider)
    if not provider.state_equal(state1, state2):
        raise AssertionError(
            "Determinism failed: same instance, same input, different states"
        )

    # Independent instance
    proj2 = provider.create_projection()
    state3 = replay_events(proj2, events, provider)
    if not provider.state_equal(state1, state3):
        raise AssertionError(
            "Determinism failed: different instances, different states"
        )
    proj2.shutdown()

    # Serialization determinism
    serialized1 = projection.serialize(state1)
    serialized2 = projection.serialize(state1)
    json1 = provider.canonical_json(serialized1)
    json2 = provider.canonical_json(serialized2)
    if json1 != json2:
        raise AssertionError(
            "Determinism failed: serialize(state) is not deterministic"
        )

    # Roundtrip determinism
    restored = projection.deserialize(serialized1)
    reserialized = projection.serialize(restored)
    json3 = provider.canonical_json(reserialized)
    if json1 != json3:
        raise AssertionError(
            "Determinism failed: serialize → deserialize → serialize "
            "produces different JSON"
        )

    return True


def verify_incrementality(
    projection: Projection,
    provider: ProjectionConformanceProvider,
) -> bool:
    """Law 4: replay(A+B) == replay(B, initial_state=replay(A)).

    Tests at multiple split points to verify incremental replay
    produces identical state to full replay.
    """
    events = provider.events()
    splits = provider.snapshot_points(events)

    # Compute full replay once
    full_state = replay_events(projection, events, provider)

    for split in splits:
        if split == 0:
            # Empty prefix: delta replay from empty events with
            # no initial state is equivalent to full replay
            continue
        if split >= len(events):
            # No delta events: initial_state should match full state
            continue

        proj = provider.create_projection()
        prefix = replay_events(proj, events[:split], provider)
        delta = replay_events(
            proj, events[split:], provider, initial_state=prefix,
        )
        if not provider.state_equal(full_state, delta):
            raise AssertionError(
                f"Incrementality failed at split {split}/{len(events)}"
            )
        proj.shutdown()

    return True


def verify_snapshot_roundtrip(
    projection: Projection,
    provider: ProjectionConformanceProvider,
) -> bool:
    """Law 3: State → snapshot → state is lossless.

    Verifies serialize → deserialize is a perfect roundtrip.
    """
    events = provider.events()
    state = replay_events(projection, events, provider)

    # Roundtrip
    serialized = projection.serialize(state)
    restored = projection.deserialize(serialized)
    if not provider.state_equal(state, restored):
        raise AssertionError(
            "Snapshot roundtrip failed: state ≠ deserialize(serialize(state))"
        )

    # Deterministic serialization
    json1 = provider.canonical_json(serialized)
    json2 = provider.canonical_json(projection.serialize(state))
    if json1 != json2:
        raise AssertionError(
            "Snapshot roundtrip failed: serialize(state) not deterministic"
        )

    return True


def verify_replay_equivalence(
    projection: Projection,
    provider: ProjectionConformanceProvider,
) -> bool:
    """Verify that full replay and delta replay produce equivalent state.

    This is a stronger test than incrementality: it verifies the
    snapshot-as-cache model (Law 3) by simulating snapshot restore
    + delta replay at multiple points.
    """
    events = provider.events()
    splits = provider.snapshot_points(events)

    # Full replay once
    full_state = replay_events(projection, events, provider)

    for split in splits:
        if split == 0 or split >= len(events):
            continue

        # Simulate snapshot at split
        proj = provider.create_projection()
        prefix = replay_events(proj, events[:split], provider)
        # Restore from snapshot (serialize → deserialize)
        snapshot = projection.serialize(prefix)
        restored = projection.deserialize(snapshot)
        # Delta from restored snapshot
        delta = replay_events(
            proj, events[split:], provider, initial_state=restored,
        )
        if not provider.state_equal(full_state, delta):
            raise AssertionError(
                f"Replay equivalence failed at split {split}/{len(events)}"
            )
        proj.shutdown()

    return True


def verify_serialization_roundtrip(
    projection: Projection,
    provider: ProjectionConformanceProvider,
) -> bool:
    """Verify serialize → JSON file → deserialize roundtrip.

    Catches subtle nondeterminism in JSON serialization that
    in-memory roundtrip might miss.
    """
    events = provider.events()
    state = replay_events(projection, events, provider)

    serialized = projection.serialize(state)

    # Write to temp file and read back
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False,
    ) as f:
        json.dump(serialized, f, sort_keys=True, indent=2)
        f.flush()
        with open(f.name) as f2:
            data = json.load(f2)

    restored = projection.deserialize(data)
    if not provider.state_equal(state, restored):
        raise AssertionError(
            "Serialization roundtrip failed: "
            "state ≠ deserialize(json.load(json.dump(serialize(state))))"
        )

    return True


def verify_health_contract(
    projection: Projection,
    provider: ProjectionConformanceProvider,
) -> bool:
    """Verify projection follows the health state machine (Law 6).

    Checks that health transitions follow the allowed pattern
    defined by the Projection Platform.
    """
    # Allowed transitions (platform-owned, not projection-specific)
    allowed_transitions: dict[str, set[str]] = {
        "unknown": {"initializing", "building", "ready"},
        "initializing": {"building", "ready"},
        "building": {"ready", "stale", "failed"},
        "ready": {"stale", "degraded", "failed", "shutdown"},
        "stale": {"building", "shutdown"},
        "degraded": {"building", "ready", "failed", "shutdown"},
        "failed": {"shutdown"},
        "shutdown": set(),
    }

    # Use a fresh projection instance
    proj = provider.create_projection()

    # Initial state should be unknown
    initial = proj.health()
    if initial not in ProjectionHealth:
        raise AssertionError(
            f"Invalid initial health: {initial}"
        )

    # Initialize
    ctx = provider.create_context(proj)
    proj.initialize(ctx)
    h = proj.health()
    if h.value not in allowed_transitions.get(initial.value, set()):
        raise AssertionError(
            f"Health transition {initial.value} → {h.value} not allowed"
        )

    # Replay to ready
    events = provider.events()
    replay_events(proj, events, provider)
    h = proj.health()
    if h != ProjectionHealth.READY:
        raise AssertionError(
            f"Expected READY after replay, got {h.value}"
        )

    # Shutdown
    proj.shutdown()
    h = proj.health()
    if h != ProjectionHealth.SHUTDOWN:
        raise AssertionError(
            f"Expected SHUTDOWN after shutdown, got {h.value}"
        )

    return True


def verify_isolation(
    projection: Projection,
    provider: ProjectionConformanceProvider,
) -> bool:
    """Law 7: Reads only declared event types.

    Verifies that replaying supported events with unsupported events
    interleaved produces the same state as replaying only supported events.
    """
    supported = provider.supported_events()
    unsupported = provider.unsupported_events()

    if not unsupported:
        # No unsupported events to test; isolation is vacuously true
        return True

    # Replay supported-only
    proj1 = provider.create_projection()
    state_supported = replay_events(proj1, supported, provider)
    proj1.shutdown()

    # Replay supported + unsupported interleaved
    mixed = _interleave(supported, unsupported)
    proj2 = provider.create_projection()
    state_mixed = replay_events(proj2, mixed, provider)
    proj2.shutdown()

    if not provider.state_equal(state_supported, state_mixed):
        raise AssertionError(
            "Isolation failed: unsupported events changed projection state"
        )

    return True


def _interleave(
    a: list[Any], b: list[Any],
) -> list[Any]:
    """Interleave two lists, preserving order within each."""
    result = []
    ai, bi = 0, 0
    while ai < len(a) or bi < len(b):
        if ai < len(a):
            result.append(a[ai])
            ai += 1
        if bi < len(b):
            result.append(b[bi])
            bi += 1
    return result
