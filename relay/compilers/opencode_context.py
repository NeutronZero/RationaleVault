"""OpenCode Context Compiler — Minimal ContextPackage compiler for OpenCode.

Renders ContextPackage into AGENTS.md-style markdown. Minimal and focused.

Section structure:
  1. Project Context (query, profile)
  2. Goals (key takeaways from knowledge citations)
  3. Decisions (decision-type citations)
  4. Constraints (invariant citations)
  5. Recent Changes (event citations)
  6. References (all citations as compact list)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from relay.compilers.compiler_output import CompilerOutput
from relay.compilers.context_compiler_base import ContextPackageCompiler

if TYPE_CHECKING:
    from relay.knowledge.context_compiler import ContextPackage
    from relay.knowledge.context_types import ContextCitation


class OpenCodeContextCompiler(ContextPackageCompiler):
    """Compiles ContextPackage into AGENTS.md-style markdown for OpenCode."""

    @property
    def agent_name(self) -> str:
        return "OpenCode"

    @property
    def format_name(self) -> str:
        return "markdown"

    def compile(self, package: ContextPackage) -> CompilerOutput:
        start = time.monotonic()

        citations = package.citations[:self.max_citations]

        sections = [
            self._header(package),
            self._goals(citations),
            self._decisions(citations),
            self._constraints(citations),
            self._recent_changes(citations),
            self._references(citations),
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
            source_counts=package.source_counts,
            compile_time_ms=round(total_ms, 2),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _header(self, package: ContextPackage) -> str:
        counts = package.source_counts
        return (
            f"# Project Context\n"
            f"**Query:** {package.query}  \n"
            f"**Profile:** {package.profile}  \n"
            f"**Sources:** {counts.get('events', 0)} events, "
            f"{counts.get('memories', 0)} memories, "
            f"{counts.get('knowledge', 0)} knowledge"
        )

    def _goals(self, citations: list[ContextCitation]) -> str:
        knowledge = [c for c in citations if c.source_type == "knowledge"]
        if not knowledge:
            return ""

        lines = ["## Goals", ""]
        for c in knowledge[:5]:
            lines.append(f"- {c.title}: {c.content[:200]}")
        return "\n".join(lines)

    def _decisions(self, citations: list[ContextCitation]) -> str:
        decisions = [
            c for c in citations
            if c.source_type in ("memory", "knowledge")
            and any(r.startswith("memory_type:DECISION") or r.startswith("knowledge_type:DECISION")
                    for r in c.reasons)
        ]
        if not decisions:
            return ""

        lines = ["## Decisions", ""]
        for c in decisions:
            lines.append(f"- **{c.title}** — {c.content[:200]}")
        return "\n".join(lines)

    def _constraints(self, citations: list[ContextCitation]) -> str:
        constraints = [
            c for c in citations
            if c.source_type == "knowledge"
            and any(r.startswith("knowledge_type:PROJECT_INVARIANT")
                    or r.startswith("knowledge_type:ARCHITECTURE_PRINCIPLE")
                    for r in c.reasons)
        ]
        if not constraints:
            return ""

        lines = ["## Constraints", ""]
        for c in constraints:
            lines.append(f"- {c.title}")
        return "\n".join(lines)

    def _recent_changes(self, citations: list[ContextCitation]) -> str:
        events = [c for c in citations if c.source_type == "event"]
        if not events:
            return ""

        lines = ["## Recent Changes", ""]
        for c in events:
            lines.append(f"- {c.title}: {c.content[:200]}")
        return "\n".join(lines)

    def _references(self, citations: list[ContextCitation]) -> str:
        if not citations:
            return ""

        lines = ["## References", ""]
        for c in citations:
            lines.append(f"- [{c.source_type}] {c.title} (`{c.source_id[:12]}`)")
        return "\n".join(lines)
