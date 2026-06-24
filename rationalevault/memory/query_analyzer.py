from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RetrievalProfile(str, Enum):
    DECISION_LOOKUP = "DECISION_LOOKUP"
    FAILURE_ANALYSIS = "FAILURE_ANALYSIS"
    ARCHITECTURE_REVIEW = "ARCHITECTURE_REVIEW"
    LESSON_DISCOVERY = "LESSON_DISCOVERY"
    WORKFLOW_RETRIEVAL = "WORKFLOW_RETRIEVAL"
    GENERAL_SEARCH = "GENERAL_SEARCH"
    KNOWLEDGE_REVIEW = "KNOWLEDGE_REVIEW"
    PROJECT_OVERVIEW = "PROJECT_OVERVIEW"
    CONTEXT_CONSTRUCTION = "CONTEXT_CONSTRUCTION"


@dataclass
class QueryIntent:
    profile: RetrievalProfile
    keywords: list[str]
    intent: str


import re

TOKEN_RE = re.compile(r"\w+")


def analyze_query(query: str) -> QueryIntent:
    """
    Analyzes raw queries to detect intent, targeted RetrievalProfile, and filters.
    """
    q_clean = query.lower().strip()
    words = TOKEN_RE.findall(q_clean)
    stopwords = {"what", "is", "a", "the", "of", "and", "in", "to", "exist", "are", "about", "for", "with", "on", "exist", "exists"}
    keywords = [w for w in words if w and w not in stopwords]

    # Map words to profiles
    decision_triggers = {"decision", "decide", "accepted", "choose", "chose", "selection", "select"}
    failure_triggers = {"fail", "failure", "error", "lost", "loss", "drift", "contradict", "contradiction", "mutation"}
    arch_triggers = {"architect", "architecture", "goal", "focus", "design", "principal", "principles", "goals"}
    lesson_triggers = {"lesson", "learned", "reflect", "reflection", "learned_pattern"}
    workflow_triggers = {"workflow", "task", "process", "pipeline", "todo"}
    knowledge_triggers = {"knowledge", "principle", "invariant", "synthesized", "pattern", "derived", "corpus"}
    overview_triggers = {"overview", "summary", "summarize", "project", "state", "status", "standing", "health"}
    context_triggers = {"context", "construct", "blend", "unified", "combined", "comprehensive", "full"}

    profile = RetrievalProfile.GENERAL_SEARCH
    intent = "general_search"

    # CONTEXT_CONSTRUCTION has highest specificity
    if any(any(t in w for t in context_triggers) for w in words):
        profile = RetrievalProfile.CONTEXT_CONSTRUCTION
        intent = "context_construction"
    elif any(any(t in w for t in decision_triggers) for w in words):
        profile = RetrievalProfile.DECISION_LOOKUP
        intent = "decision_lookup"
    elif any(any(t in w for t in failure_triggers) for w in words):
        profile = RetrievalProfile.FAILURE_ANALYSIS
        intent = "failure_analysis"
    elif any(any(t in w for t in arch_triggers) for w in words):
        profile = RetrievalProfile.ARCHITECTURE_REVIEW
        intent = "architecture_review"
    elif any(any(t in w for t in knowledge_triggers) for w in words):
        profile = RetrievalProfile.KNOWLEDGE_REVIEW
        intent = "knowledge_review"
    elif any(any(t in w for t in overview_triggers) for w in words):
        profile = RetrievalProfile.PROJECT_OVERVIEW
        intent = "project_overview"
    elif any(any(t in w for t in lesson_triggers) for w in words):
        profile = RetrievalProfile.LESSON_DISCOVERY
        intent = "lesson_discovery"
    elif any(any(t in w for t in workflow_triggers) for w in words):
        profile = RetrievalProfile.WORKFLOW_RETRIEVAL
        intent = "workflow_retrieval"

    return QueryIntent(
        profile=profile,
        keywords=keywords,
        intent=intent
    )

