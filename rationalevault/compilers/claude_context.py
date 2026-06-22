"""Claude Context Compiler — Full ContextPackage compiler for Claude.

Renders ContextPackage into structured markdown optimized for Claude's
narrative reasoning style. Profile-aware: different queries produce
different section emphasis.

Section structure:
  1. Header (query, profile, source counts)
  2. Critical Constraints (PROJECT_INVARIANT, ARCHITECTURE_PRINCIPLE, critical memories)
  3. Decisions & Rationale (decision-type memories and knowledge)
  4. Architecture & Design (architecture knowledge)
  5. Recent Activity (event citations)
  6. Relevant Memories (non-decision memory citations)
  7. Source Traceability (citation provenance mapping)

Design:
  - Output-only. No Anthropic API calls. RationaleVault is model-agnostic.
  - Paste the output at the top of a Claude conversation.
  - Profile determines section ordering and emphasis.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from rationalevault.compilers.compiler_output import CompilerOutput
from rationalevault.compilers.context_compiler_base import ContextPackageCompiler

if TYPE_CHECKING:
    from rationalevault.knowledge.context_compiler import ContextPackage
    from rationalevault.knowledge.context_types import ContextCitation

_PROFILE_ICONS = {
    "DECISION_LOOKUP": "🔍",
    "FAILURE_ANALYSIS": "🔴",
    "ARCHITECTURE_REVIEW": "🏗️",
    "KNOWLEDGE_REVIEW": "📚",
    "PROJECT_OVERVIEW": "🗺️",
    "CONTEXT_CONSTRUCTION": "🔧",
    "LESSON_DISCOVERY": "💡",
    "WORKFLOW_RETRIEVAL": "🔄",
    "GENERAL_SEARCH": "🔎",
}

_CONSTRAINT_TYPES = {"PROJECT_INVARIANT", "ARCHITECTURE_PRINCIPLE"}
_CRITICAL_MEMORY_TYPES = {"DECISION", "DECISION_RATIONALE", "ARCHITECTURE"}
_DECISION_KNOWLEDGE_TYPES = {"DECISION_LINEAGE", "ARCHITECTURE_PRINCIPLE", "PROJECT_INVARIANT"}
_ARCHITECTURE_KNOWLEDGE_TYPES = {"ARCHITECTURE_PRINCIPLE", "PROJECT_INVARIANT", "LESSON"}


class ClaudeContextCompiler(ContextPackageCompiler):
    """Compiles ContextPackage into markdown optimized for Claude.

    Profile-aware: adapts section ordering and emphasis based on
    the retrieval profile used to build the context package.
    """

    @property
    def agent_name(self) -> str:
        return "Claude"

    @property
    def format_name(self) -> str:
        return "markdown"

    def compile(self, package: ContextPackage) -> CompilerOutput:
        start = time.monotonic()

        citations = package.citations[:self.max_citations]
        source_counts = package.source_counts

        sections = [
            self._header(package),
            self._critical_constraints(citations),
            self._decisions_and_rationale(citations),
            self._architecture_and_design(citations),
            self._recent_activity(citations),
            self._relevant_memories(citations),
            self._source_traceability(citations) if self.include_provenance else "",
        ]

        rendered = "\n\n".join(s for s in sections if s.strip())

        elapsed_ms = (time.monotonic() - start) * 1000
        total_ms = package.timing.get("total_ms", elapsed_ms)

        return CompilerOutput(
            query=package.query,
            profile=package.profile,
            agent=self.agent_name,
            format_name=self.format_name,
            rendered_content=rendered,
            citation_count=len(citations),
            source_counts=source_counts,
            compile_time_ms=round(total_ms, 2),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _header(self, package: ContextPackage) -> str:
        icon = _PROFILE_ICONS.get(package.profile, "🔎")
        counts = package.source_counts
        return (
            f"# {icon} Project Context\n"
            f"> **Query:** {package.query}\n"
            f"> **Profile:** {package.profile}\n"
            f"> **Sources:** {counts.get('events', 0)} events, "
            f"{counts.get('memories', 0)} memories, "
            f"{counts.get('knowledge', 0)} knowledge\n"
            f">\n"
            f"> ⚡ This context was retrieved by RationaleVault. "
            f"Do **not** re-derive information already present here."
        )

    def _critical_constraints(self, citations: list[ContextCitation]) -> str:
        constraints = []
        for c in citations:
            if c.source_type == "knowledge":
                ktype = self._extract_knowledge_type(c)
                if ktype in _CONSTRAINT_TYPES:
                    constraints.append(c)
            elif c.source_type == "memory":
                mtype = self._extract_memory_type(c)
                if mtype in _CRITICAL_MEMORY_TYPES:
                    constraints.append(c)

        if not constraints:
            return (
                "## Critical Constraints\n"
                "_No critical constraints identified for this query._"
            )

        lines = [
            "## Critical Constraints",
            "",
            "> These are non-negotiable project invariants and architectural principles.",
            "> Do **not** violate these without explicit justification.",
        ]
        for c in constraints:
            source_label = self._source_label(c)
            lines.append(f"\n### {c.title}")
            lines.append(f"**Source:** {source_label}  |  **Confidence:** {c.confidence:.0%}")
            if c.content:
                lines.append(f"\n{c.content}")

        return "\n".join(lines)

    def _decisions_and_rationale(self, citations: list[ContextCitation]) -> str:
        decisions = []
        for c in citations:
            if c.source_type == "knowledge":
                ktype = self._extract_knowledge_type(c)
                if ktype in _DECISION_KNOWLEDGE_TYPES and ktype not in _CONSTRAINT_TYPES:
                    decisions.append(c)
            elif c.source_type == "memory":
                mtype = self._extract_memory_type(c)
                if mtype in {"DECISION", "DECISION_RATIONALE"} and mtype not in _CRITICAL_MEMORY_TYPES:
                    decisions.append(c)

        if not decisions:
            return (
                "## Decisions & Rationale\n"
                "_No relevant decisions found for this query._"
            )

        lines = [
            "## Decisions & Rationale",
            "",
            "> These decisions are relevant to your query.",
            "> Review before making changes that might conflict.",
        ]
        for c in decisions:
            source_label = self._source_label(c)
            lines.append(f"\n### {c.title}")
            lines.append(f"**Source:** {source_label}  |  **Confidence:** {c.confidence:.0%}")
            if c.content:
                lines.append(f"\n{c.content}")

        return "\n".join(lines)

    def _architecture_and_design(self, citations: list[ContextCitation]) -> str:
        arch = []
        for c in citations:
            if c.source_type == "knowledge":
                ktype = self._extract_knowledge_type(c)
                if ktype in _ARCHITECTURE_KNOWLEDGE_TYPES and ktype not in _CONSTRAINT_TYPES and ktype not in _DECISION_KNOWLEDGE_TYPES:
                    arch.append(c)
            elif c.source_type == "memory":
                mtype = self._extract_memory_type(c)
                if mtype == "ARCHITECTURE" and mtype not in _CRITICAL_MEMORY_TYPES:
                    arch.append(c)

        if not arch:
            return (
                "## Architecture & Design\n"
                "_No architecture-specific context found for this query._"
            )

        lines = [
            "## Architecture & Design",
            "",
            "> Design patterns and architectural context relevant to your query.",
        ]
        for c in arch:
            source_label = self._source_label(c)
            lines.append(f"\n### {c.title}")
            lines.append(f"**Source:** {source_label}  |  **Confidence:** {c.confidence:.0%}")
            if c.content:
                lines.append(f"\n{c.content}")

        return "\n".join(lines)

    def _recent_activity(self, citations: list[ContextCitation]) -> str:
        events = [c for c in citations if c.source_type == "event"]

        if not events:
            return (
                "## Recent Activity\n"
                "_No relevant recent events found for this query._"
            )

        lines = [
            "## Recent Activity",
            "",
            "> Recent events relevant to your query.",
        ]
        for c in events:
            lines.append(f"\n- **{c.title}**")
            if c.content:
                lines.append(f"  {c.content}")
            if c.reasons:
                lines.append(f"  _Reason:_ {c.reasons[0]}")

        return "\n".join(lines)

    def _relevant_memories(self, citations: list[ContextCitation]) -> str:
        memories = []
        for c in citations:
            if c.source_type == "memory":
                mtype = self._extract_memory_type(c)
                if mtype not in _CRITICAL_MEMORY_TYPES:
                    memories.append(c)

        if not memories:
            return (
                "## Relevant Memories\n"
                "_No additional memories found for this query._"
            )

        lines = [
            "## Relevant Memories",
            "",
            "> Retrieved memories relevant to your query.",
        ]
        for c in memories:
            source_label = self._source_label(c)
            lines.append(f"\n### {c.title}")
            lines.append(f"**Source:** {source_label}  |  **Relevance:** {c.relevance_score:.2f}")
            if c.content:
                lines.append(f"\n{c.content}")

        return "\n".join(lines)

    def _source_traceability(self, citations: list[ContextCitation]) -> str:
        lines = [
            "## Source Traceability",
            "",
            "> Every citation traces back to source events.",
        ]
        for c in citations:
            if c.source_event_ids:
                events = ", ".join(f"`{e}`" for e in c.source_event_ids)
                lines.append(f"- **{c.title}** ({c.source_type}) → {events}")

        return "\n".join(lines)

    @staticmethod
    def _extract_knowledge_type(citation: ContextCitation) -> str:
        for reason in citation.reasons:
            if reason.startswith("knowledge_type:"):
                return reason.split(":", 1)[1]
        return ""

    @staticmethod
    def _extract_memory_type(citation: ContextCitation) -> str:
        for reason in citation.reasons:
            if reason.startswith("memory_type:"):
                return reason.split(":", 1)[1]
        return ""

    @staticmethod
    def _source_label(citation: ContextCitation) -> str:
        return f"{citation.source_type}/{citation.source_id[:12]}"
