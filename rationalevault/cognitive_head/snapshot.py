"""
RationaleVault Snapshot Manager — Load, validate, save, and manage projection snapshots.

V2 IMPLEMENTATION:
  - SnapshotManager: orchestrates load, validate, save, policy, warnings.
  - NullSnapshotManager: no-op implementation for when snapshots are disabled.
  - SnapshotStore: raw storage interface.
  - SnapshotValidationResult: typed result with reason enum.
  - Storage does not validate; validation is the manager's responsibility.

Thread safety: Implementations must be safe for concurrent reads.
Writes are serialized by the database (SQLite WAL / PostgreSQL advisory locks).
"""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from rationalevault.cognitive_head.snapshot_payload import (
    CognitiveHeadSnapshotPayload,
    ProjectionSnapshotPayload,
)
from rationalevault.cognitive_head.snapshot_policy import (
    SnapshotPolicy,
)


# ── Validation Types ─────────────────────────────────────────────────────────


class SnapshotValidationReason(Enum):
    """Why a snapshot was rejected during validation."""

    NOT_FOUND = "not_found"
    HASH_MISMATCH = "hash_mismatch"
    SCHEMA_VERSION = "schema_version_mismatch"
    PROJECTION_VERSION = "projection_version_mismatch"
    FUTURE_SEQUENCE = "sequence_ahead_of_events"
    DESERIALIZATION = "deserialization_failed"


@dataclass
class SnapshotValidationResult:
    """
    Typed result from snapshot validation.

    Attributes:
        valid:  Whether the snapshot passed all checks.
        payload: The deserialized payload (only set when valid=True).
        reason: Why validation failed (only set when valid=False).
    """
    valid: bool
    payload: Optional[ProjectionSnapshotPayload] = None
    reason: Optional[SnapshotValidationReason] = None


# ── Serializer Registry ──────────────────────────────────────────────────────

# Maps projection_name → payload class.
# To add a new projection (knowledge, organization), add one entry here.
SNAPSHOT_SERIALIZERS: dict[str, type[ProjectionSnapshotPayload]] = {
    "cognitive_head": CognitiveHeadSnapshotPayload,
}


# ── Storage Interface ────────────────────────────────────────────────────────


class SnapshotStore(ABC):
    """
    Raw storage interface for projection snapshots.

    Storage does NOT validate. It returns raw data; the SnapshotManager
    handles deserialization and validation.
    """

    @abstractmethod
    def load_latest_raw(
        self,
        project_id: UUID,
        projection_name: str,
    ) -> Optional[dict[str, Any]]:
        """
        Return the raw payload row for the latest snapshot, or None.

        Returns a dict with keys: payload, schema_version,
        projection_version, sequence, snapshot_hash.
        """
        pass

    @abstractmethod
    def save_snapshot(
        self,
        project_id: UUID,
        projection_name: str,
        payload: ProjectionSnapshotPayload,
    ) -> None:
        """
        Persist a snapshot to durable storage.

        Old snapshots are retained for audit (not deleted on save).
        """
        pass

    @abstractmethod
    def delete_snapshots_before(
        self,
        project_id: UUID,
        projection_name: str,
        sequence: int,
    ) -> int:
        """
        Delete snapshots older than the given sequence number.
        Returns the number of snapshots deleted.
        """
        pass

    @abstractmethod
    def get_latest_snapshot_sequence(
        self,
        project_id: UUID,
        projection_name: str,
    ) -> Optional[int]:
        """
        Return the sequence number of the latest snapshot, or None.
        """
        pass


# ── Snapshot Manager ─────────────────────────────────────────────────────────


class SnapshotManager:
    """
    Orchestrates snapshot loading, validation, policy evaluation, and saving.

    The compiler calls load_valid_snapshot() for the fast path, and
    refresh_snapshot() after compilation to let the manager decide whether
    to persist a new snapshot.

    The compiler never touches hashes, schema versions, policy, or serialization.
    """

    def __init__(
        self,
        snapshot_store: SnapshotStore,
        get_latest_sequence_fn,
        policy: Optional[SnapshotPolicy] = None,
    ) -> None:
        """
        Args:
            snapshot_store: The raw storage backend.
            get_latest_sequence_fn: Callable(project_id) → int
                Returns the max event_sequence for a project.
            policy: Trigger policy for snapshot saves. Uses DEFAULT_POLICY if None.
        """
        self._store = snapshot_store
        self._get_latest_sequence = get_latest_sequence_fn
        # Import here to avoid circular imports at module level
        from rationalevault.cognitive_head.snapshot_policy import DEFAULT_POLICY
        self._policy = policy if policy is not None else DEFAULT_POLICY

    def load_valid_snapshot(
        self,
        project_id: UUID,
        projection_name: str = "cognitive_head",
    ) -> SnapshotValidationResult:
        """
        Load, deserialize, and validate the latest snapshot.

        Returns SnapshotValidationResult with:
          - valid=True, payload=... (caller should use the payload)
          - valid=False, reason=... (caller should fall back to full replay)
        """
        # 1. Load raw
        raw = self._store.load_latest_raw(project_id, projection_name)
        if raw is None:
            return SnapshotValidationResult(
                valid=False,
                reason=SnapshotValidationReason.NOT_FOUND,
            )

        # 2. Resolve serializer
        serializer = SNAPSHOT_SERIALIZERS.get(projection_name)
        if serializer is None:
            return SnapshotValidationResult(
                valid=False,
                reason=SnapshotValidationReason.DESERIALIZATION,
            )

        # 3. Deserialize
        try:
            payload = serializer.from_dict(raw["payload"])
        except (KeyError, TypeError, ValueError, AttributeError):
            return SnapshotValidationResult(
                valid=False,
                reason=SnapshotValidationReason.DESERIALIZATION,
            )

        # 4. Validate hash
        if not payload.validate_hash():
            return SnapshotValidationResult(
                valid=False,
                reason=SnapshotValidationReason.HASH_MISMATCH,
            )

        # 5. Check schema_version
        if payload.schema_version != serializer.SCHEMA_VERSION:
            return SnapshotValidationResult(
                valid=False,
                reason=SnapshotValidationReason.SCHEMA_VERSION,
            )

        # 6. Check projection_version
        if payload.projection_version != serializer.PROJECTION_VERSION:
            return SnapshotValidationResult(
                valid=False,
                reason=SnapshotValidationReason.PROJECTION_VERSION,
            )

        # 7. Check sequence ≤ latest event
        latest_seq = self._get_latest_sequence(project_id)
        if payload.sequence > latest_seq:
            return SnapshotValidationResult(
                valid=False,
                reason=SnapshotValidationReason.FUTURE_SEQUENCE,
            )

        # All checks passed
        return SnapshotValidationResult(valid=True, payload=payload)

    def warn_invalid(
        self,
        project_id: UUID,
        result: SnapshotValidationResult,
    ) -> None:
        """Emit a warning to stderr for an invalid snapshot."""
        if result.valid or result.reason is None:
            return
        print(
            f"[rationalevault] WARN: Ignoring invalid snapshot for "
            f"project {project_id} "
            f"(reason={result.reason.value}); "
            f"falling back to full replay.",
            file=sys.stderr,
        )

    def refresh_snapshot(
        self,
        project_id: UUID,
        projection_name: str,
        head: CognitiveHeadSnapshotPayload,
        current_sequence: int,
    ) -> None:
        """
        Evaluate policy and save a snapshot if needed.

        This is the only public method called by the compiler after compilation.
        Never raises an exception that would affect the caller.
        """
        try:
            last_seq = self._store.get_latest_snapshot_sequence(
                project_id, projection_name,
            )
            if not self._policy.should_snapshot(current_sequence, last_seq):
                return

            # Build immutable payload with hash
            hashed = head.with_hash()
            self._store.save_snapshot(project_id, projection_name, hashed)

        except Exception as e:
            # Snapshots are caches; never fail compilation.
            print(
                f"[rationalevault] WARN: Snapshot save failed for "
                f"{project_id}/{projection_name}: {e}",
                file=sys.stderr,
            )


# ── Null Object ──────────────────────────────────────────────────────────────


class NullSnapshotManager(SnapshotManager):
    """No-op snapshot manager. All operations are silent no-ops."""

    def __init__(self) -> None:
        # Do not require a real store; this is a null object.
        pass

    def load_valid_snapshot(
        self,
        project_id: UUID,
        projection_name: str = "cognitive_head",
    ) -> SnapshotValidationResult:
        return SnapshotValidationResult(
            valid=False,
            reason=SnapshotValidationReason.NOT_FOUND,
        )

    def warn_invalid(
        self,
        project_id: UUID,
        result: SnapshotValidationResult,
    ) -> None:
        pass

    def refresh_snapshot(
        self,
        project_id: UUID,
        projection_name: str,
        head: CognitiveHeadSnapshotPayload,
        current_sequence: int,
    ) -> None:
        pass
