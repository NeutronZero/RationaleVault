from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from rationalevault.canonical.envelope import CanonicalEnvelope
from rationalevault.canonical.payload import CanonicalPayload
from rationalevault.canonical.timestamp import CanonicalTimestamp
from rationalevault.canonical.types import EventType
from rationalevault.ledger.commit import CommitBuilder
from rationalevault.ledger.errors import DuplicateCommitError
from rationalevault.ledger.interface import Ledger

if TYPE_CHECKING:
    from rationalevault.ledger.commit import Commit, CommitReceipt


@dataclass(frozen=True)
class ComplianceCheckResult:
    passed: bool
    message: str
    expected: str | None = None
    actual: str | None = None


DEFAULT_TIMESTAMP = CanonicalTimestamp.from_datetime(
    datetime(2026, 7, 14, 0, 0, 0, tzinfo=timezone.utc)
)


def _resolve_event_type(raw: str | None) -> EventType:
    mapping = {
        "decision_recorded": EventType.DECISION_RECORDED,
        "evaluation_recorded": EventType.EVALUATION_RECORDED,
        "knowledge_updated": EventType.KNOWLEDGE_UPDATED,
        "experience_recorded": EventType.EXPERIENCE_RECORDED,
        "outcome_observed": EventType.OUTCOME_OBSERVED,
    }
    if raw in mapping:
        return mapping[raw]
    return EventType.DECISION_RECORDED


def _make_envelope(
    stream_id: str,
    sequence: int,
    event_type: str,
    payload: dict[str, Any] | None = None,
    experience_id: str = "exp-test",
) -> CanonicalEnvelope:
    return CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id=experience_id,
        event_type=_resolve_event_type(event_type),
        stream_id=stream_id,
        sequence=sequence,
        timestamp=DEFAULT_TIMESTAMP,
        actor="compliance-test",
        payload=CanonicalPayload(data=payload or {}),
    )


def _parse_event(raw: dict[str, Any], stream_id: str, experience_id: str) -> CanonicalEnvelope:
    event_type = raw.get("event_type", "core/TestEvent")
    payload = raw.get("payload", {})
    ts_raw = raw.get("timestamp")
    if ts_raw and "iso" in ts_raw:
        ts = CanonicalTimestamp.from_iso_string(ts_raw["iso"])
    else:
        ts = DEFAULT_TIMESTAMP
    return CanonicalEnvelope(
        rvcj_version=1,
        event_schema_version=1,
        experience_id=experience_id,
        event_type=_resolve_event_type(event_type),
        stream_id=stream_id,
        sequence=raw["sequence"],
        timestamp=ts,
        actor="compliance-test",
        payload=CanonicalPayload(data=payload),
    )


class LedgerComplianceValidator:
    def __init__(self, ledger_factory):
        self._ledger_factory = ledger_factory

    def validate_vector(self, vector: dict[str, Any]) -> list[ComplianceCheckResult]:
        ledger = self._ledger_factory()
        results: list[ComplianceCheckResult] = []
        receipts: list[CommitReceipt] = []
        commits: list[Commit] = []

        for step in vector.get("setup", []):
            op = step["op"]
            if op == "append":
                commit = self._build_commit(step)
                commits.append(commit)
                try:
                    receipt = ledger.append(commit)
                    receipts.append(receipt)
                except DuplicateCommitError as e:
                    receipts.append(e.existing_receipt)
                except Exception as e:
                    results.append(
                        ComplianceCheckResult(
                            False,
                            f"Setup append failed: {e}",
                            actual=str(e),
                        )
                    )
                    return results
            elif op == "idempotent_append":
                idx = step.get("commit_index", 0)
                if idx >= len(commits):
                    results.append(
                        ComplianceCheckResult(
                            False,
                            f"Cannot idempotent append: commit_index {idx} out of range",
                        )
                    )
                    return results
                commit_to_repeat = commits[idx]
                try:
                    r2 = ledger.append(commit_to_repeat)
                    if r2 != receipts[idx]:
                        results.append(
                            ComplianceCheckResult(
                                False,
                                "Idempotent append returned different receipt",
                                expected=str(receipts[idx]),
                                actual=str(r2),
                            )
                        )
                except Exception as e:
                    results.append(
                        ComplianceCheckResult(
                            False, f"Idempotent append raised: {e}", actual=str(e)
                        )
                    )
                    return results

        for check in vector.get("checks", []):
            op = check["op"]
            if op == "read_stream":
                self._check_read_stream(ledger, check, results)
            elif op == "read_from":
                self._check_read_from(ledger, check, results)
            elif op == "exists":
                self._check_exists(ledger, check, receipts, results)
            elif op == "stream_exists":
                self._check_stream_exists(ledger, check, results)
            elif op == "idempotent_append":
                pass
            else:
                results.append(
                    ComplianceCheckResult(False, f"Unknown check op: {op}")
                )

        return results

    def _build_commit(self, step: dict[str, Any]) -> Commit:
        stream_id = step["stream_id"]
        experience_id = step.get("experience_id", "exp-test")
        raw_events = step["events"]
        envelopes = [
            _parse_event(e, stream_id, experience_id) for e in raw_events
        ]
        return CommitBuilder.from_events(stream_id, envelopes)

    def _check_read_stream(
        self,
        ledger: Ledger,
        check: dict[str, Any],
        results: list[ComplianceCheckResult],
    ) -> None:
        stream_id = check["stream_id"]
        entries = ledger.read_stream(stream_id)
        expect_count = check.get("expect_count")
        expect_sequences = check.get("expect_sequences")

        if expect_count is not None and len(entries) != expect_count:
            results.append(
                ComplianceCheckResult(
                    False,
                    f"read_stream({stream_id!r}) count mismatch",
                    expected=str(expect_count),
                    actual=str(len(entries)),
                )
            )
            return

        if expect_sequences is not None:
            actual_seqs = [e.sequence for e in entries]
            if actual_seqs != expect_sequences:
                results.append(
                    ComplianceCheckResult(
                        False,
                        f"read_stream({stream_id!r}) sequence order mismatch",
                        expected=str(expect_sequences),
                        actual=str(actual_seqs),
                    )
                )
                return

        results.append(
            ComplianceCheckResult(
                True,
                f"read_stream({stream_id!r}) OK: count={len(entries)}",
            )
        )

    def _check_read_from(
        self,
        ledger: Ledger,
        check: dict[str, Any],
        results: list[ComplianceCheckResult],
    ) -> None:
        from_go = check.get("from_global_order", 0)
        entries = ledger.read_from(from_go)
        expect_count = check.get("expect_count")

        if expect_count is not None and len(entries) != expect_count:
            results.append(
                ComplianceCheckResult(
                    False,
                    f"read_from({from_go}) count mismatch",
                    expected=str(expect_count),
                    actual=str(len(entries)),
                )
            )
            return

        results.append(
            ComplianceCheckResult(
                True,
                f"read_from({from_go}) OK: count={len(entries)}",
            )
        )

    def _check_exists(
        self,
        ledger: Ledger,
        check: dict[str, Any],
        receipts: list[CommitReceipt],
        results: list[ComplianceCheckResult],
    ) -> None:
        commit_id = check.get("commit_id")
        if commit_id is None:
            if not receipts:
                results.append(
                    ComplianceCheckResult(
                        False, "exists check requires commit_id or prior receipts"
                    )
                )
                return
            commit_id = receipts[-1].commit_id
        actual = ledger.exists(commit_id)
        expect = check.get("expect_exists", True)
        if actual != expect:
            results.append(
                ComplianceCheckResult(
                    False,
                    f"exists({commit_id}) mismatch",
                    expected=str(expect),
                    actual=str(actual),
                )
            )
            return
        results.append(
            ComplianceCheckResult(
                True, f"exists({commit_id}) OK: {actual}"
            )
        )

    def _check_stream_exists(
        self,
        ledger: Ledger,
        check: dict[str, Any],
        results: list[ComplianceCheckResult],
    ) -> None:
        stream_id = check["stream_id"]
        actual = ledger.stream_exists(stream_id)
        expect = check.get("expect_exists", True)
        if actual != expect:
            results.append(
                ComplianceCheckResult(
                    False,
                    f"stream_exists({stream_id!r}) mismatch",
                    expected=str(expect),
                    actual=str(actual),
                )
            )
            return
        results.append(
            ComplianceCheckResult(
                True, f"stream_exists({stream_id!r}) OK: {actual}"
            )
        )
