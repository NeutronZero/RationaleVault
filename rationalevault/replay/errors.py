"""Replay domain exceptions — error types for AF-003 Replay Engine contract violations."""

from __future__ import annotations


class ReplayError(Exception):
    """Base exception for all Replay Engine errors."""


class ReducerError(ReplayError):
    """Raised when a reducer violates its contract (I-12)."""


class PurityViolationError(ReducerError):
    """Raised when a reducer mutates its inputs (I-12 violation)."""
