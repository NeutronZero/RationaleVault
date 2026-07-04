"""
Tests for RationaleVault AI Advisory (F2).

Covers AdvisoryReport and AdvisoryRequest models, ID generation, serialization,
and the advisory-only principle.
"""
from __future__ import annotations

import pytest

from rationalevault.knowledge.advisory import (
    AdvisoryReport,
    AdvisoryRequest,
    AdvisoryType,
    AdvisoryConfidence,
)


# =====================================================================
# AdvisoryReport
# =====================================================================

class TestAdvisoryReport:
    def test_id_generation_deterministic(self):
        id1 = AdvisoryReport.generate_report_id("REFLECTION_SUMMARY", "Test", "2026-06-26T12:00:00Z")
        id2 = AdvisoryReport.generate_report_id("REFLECTION_SUMMARY", "Test", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("ADVCS-")

    def test_id_varies_by_type(self):
        id1 = AdvisoryReport.generate_report_id("REFLECTION_SUMMARY", "Test", "2026-06-26T12:00:00Z")
        id2 = AdvisoryReport.generate_report_id("PROMOTION_SUGGESTION", "Test", "2026-06-26T12:00:00Z")
        assert id1 != id2

    def test_serialization_roundtrip(self):
        report = AdvisoryReport(
            report_id="ADVCS-TEST",
            advisory_type=AdvisoryType.REFLECTION_SUMMARY,
            confidence=AdvisoryConfidence.HIGH,
            summary="Test summary",
            details="Test details",
            source_ids=["REFL-001", "LEARN-001"],
            recommendations=["Consider promoting to knowledge"],
            warnings=[],
            created_at="2026-06-26T12:00:00Z",
            model_version="gpt-4",
        )
        d = report.to_dict()
        restored = AdvisoryReport.from_dict(d)
        assert restored.report_id == report.report_id
        assert restored.advisory_type == report.advisory_type
        assert restored.confidence == report.confidence
        assert restored.source_ids == report.source_ids

    def test_frozen(self):
        report = AdvisoryReport(
            report_id="ADVCS-TEST",
            advisory_type=AdvisoryType.REFLECTION_SUMMARY,
            confidence=AdvisoryConfidence.MEDIUM,
            summary="Test",
            details="Test",
            source_ids=[],
            recommendations=[],
            warnings=[],
            created_at="2026-06-26T12:00:00Z",
        )
        with pytest.raises(AttributeError):
            report.summary = "Modified"

    def test_all_advisory_types(self):
        for at in AdvisoryType:
            report = AdvisoryReport(
                report_id="ADVCS-TEST",
                advisory_type=at,
                confidence=AdvisoryConfidence.MEDIUM,
                summary="Test",
                details="Test",
                source_ids=[],
                recommendations=[],
                warnings=[],
                created_at="2026-06-26T12:00:00Z",
            )
            assert report.advisory_type == at


# =====================================================================
# AdvisoryRequest
# =====================================================================

class TestAdvisoryRequest:
    def test_serialization_roundtrip(self):
        request = AdvisoryRequest(
            request_id="REQ-TEST",
            advisory_type=AdvisoryType.CONFLICT_ANALYSIS,
            context_ids=["KNOW-001", "KNOW-002"],
            question="Are these knowledge objects conflicting?",
            created_at="2026-06-26T12:00:00Z",
        )
        d = request.to_dict()
        restored = AdvisoryRequest.from_dict(d)
        assert restored.request_id == request.request_id
        assert restored.advisory_type == request.advisory_type
        assert restored.context_ids == request.context_ids

    def test_frozen(self):
        request = AdvisoryRequest(
            request_id="REQ-TEST",
            advisory_type=AdvisoryType.KNOWLEDGE_ASSESSMENT,
            context_ids=[],
            question="Test",
            created_at="2026-06-26T12:00:00Z",
        )
        with pytest.raises(AttributeError):
            request.question = "Modified"
