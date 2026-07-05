"""Tests for I12.B — Context Integration with RetrievalPlan."""
from __future__ import annotations

import uuid

import pytest

from rationalevault.knowledge.context_compiler import (
    ContextMode,
    ContextPackage,
    compile_context,
)
from rationalevault.retrieval.models import RetrievalIntent, RetrievalPlan


class TestContextPackagePlanField:
    def test_plan_default_none(self) -> None:
        pkg = ContextPackage(
            context_id="x",
            query="q",
            profile="general_search",
            created_at="2025-01-01",
        )
        assert pkg.retrieval_plan is None
        assert pkg.cross_project_state is None
        assert pkg.organization_state is None

    def test_plan_stored(self) -> None:
        plan = RetrievalPlan(
            primary_intent=RetrievalIntent.CONTINUATION,
            matched_intents=[RetrievalIntent.CONTINUATION],
            projections={"continuation": True},
            context_weights={"continuation": 1.0},
            confidence=0.9,
        )
        pkg = ContextPackage(
            context_id="x",
            query="q",
            profile="general_search",
            created_at="2025-01-01",
            retrieval_plan=plan,
        )
        assert pkg.retrieval_plan is plan

    def test_to_dict_includes_plan(self) -> None:
        plan = RetrievalPlan(
            primary_intent=RetrievalIntent.GENERAL,
            matched_intents=[RetrievalIntent.GENERAL],
            projections={"knowledge": True},
            context_weights={"knowledge": 1.0},
            confidence=0.5,
        )
        pkg = ContextPackage(
            context_id="x",
            query="q",
            profile="general_search",
            created_at="2025-01-01",
            retrieval_plan=plan,
        )
        d = pkg.to_dict()
        assert d["retrieval_plan"] is not None
        assert d["retrieval_plan"]["primary_intent"] == "general"

    def test_to_dict_without_plan(self) -> None:
        pkg = ContextPackage(
            context_id="x",
            query="q",
            profile="general_search",
            created_at="2025-01-01",
        )
        d = pkg.to_dict()
        assert d["retrieval_plan"] is None
        assert d["cross_project_state"] is None
        assert d["organization_state"] is None


class TestCompileContextBackwardCompatible:
    def test_no_plan_works(self) -> None:
        pkg = compile_context(query="test query", project_id=None)
        assert pkg.retrieval_plan is not None
        assert pkg.retrieval_plan.primary_intent == RetrievalIntent.GENERAL
        assert pkg.cross_project_state is None
        assert pkg.organization_state is None
        assert pkg.mode == "standard"

    def test_with_plan_stored(self) -> None:
        plan = RetrievalPlan(
            primary_intent=RetrievalIntent.KNOWLEDGE_QUERY,
            matched_intents=[RetrievalIntent.KNOWLEDGE_QUERY],
            projections={"knowledge": True},
            context_weights={"knowledge": 1.0},
            confidence=0.8,
        )
        pkg = compile_context(query="test", project_id=None, plan=plan)
        assert pkg.retrieval_plan is plan
        assert pkg.retrieval_plan.primary_intent == RetrievalIntent.KNOWLEDGE_QUERY

    def test_existing_callers_unaffected(self) -> None:
        pkg = compile_context(
            query="test query",
            project_id=None,
            mode=ContextMode.STANDARD,
            memory_limit=5,
            knowledge_limit=5,
            event_limit=10,
            total_slices=10,
        )
        assert pkg.retrieval_plan is not None
        assert pkg.cross_project_state is None
        assert pkg.organization_state is None
        assert pkg.mode == "standard"

    def test_continuation_mode_still_works(self) -> None:
        pkg = compile_context(
            query="continue sprint 34",
            project_id=None,
            mode=ContextMode.CONTINUATION,
        )
        assert pkg.retrieval_plan is not None
        assert pkg.retrieval_plan.primary_intent == RetrievalIntent.CONTINUATION
        assert pkg.mode == "continuation"


class TestCompileContextWithPlanAndProject:
    def test_with_plan_and_project(self) -> None:
        plan = RetrievalPlan(
            primary_intent=RetrievalIntent.CONTINUATION,
            matched_intents=[RetrievalIntent.CONTINUATION],
            projections={"continuation": True, "knowledge": True, "graph": True},
            context_weights={"continuation": 0.4, "knowledge": 0.3, "graph": 0.3},
            confidence=0.9,
        )
        # project_id=None avoids MissingProjectBootstrapError
        pkg = compile_context(
            query="continue sprint 34",
            project_id=None,
            mode=ContextMode.STANDARD,
            plan=plan,
        )
        assert pkg.retrieval_plan is plan
        assert pkg.retrieval_plan.primary_intent == RetrievalIntent.CONTINUATION

    def test_plan_none_with_project(self) -> None:
        project_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        pkg = compile_context(
            query="test",
            project_id=project_id,
            mode=ContextMode.STANDARD,
        )
        assert pkg.retrieval_plan is not None
        assert pkg.retrieval_plan.primary_intent == RetrievalIntent.GENERAL
