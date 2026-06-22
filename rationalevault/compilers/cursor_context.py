"""Cursor Context Compiler — Minimal ContextPackage compiler for Cursor.

Renders ContextPackage as YAML with full provenance traceability.
Cursor workflows depend on traceability, so every citation includes
source event IDs.
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


class CursorContextCompiler(ContextPackageCompiler):
    """Compiles ContextPackage into YAML format for Cursor."""

    @property
    def agent_name(self) -> str:
        return "Cursor"

    @property
    def format_name(self) -> str:
        return "yaml"

    def compile(self, package: ContextPackage) -> CompilerOutput:
        start = time.monotonic()

        citations = package.citations[:self.max_citations]
        rendered = self._render_yaml(package, citations)

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

    def _render_yaml(self, package: ContextPackage, citations: list[ContextCitation]) -> str:
        lines = [
            f"query: \"{self._escape_yaml(package.query)}\"",
            f"profile: \"{package.profile}\"",
            f"context_id: \"{package.context_id}\"",
            f"source_counts:",
            f"  events: {package.source_counts.get('events', 0)}",
            f"  memories: {package.source_counts.get('memories', 0)}",
            f"  knowledge: {package.source_counts.get('knowledge', 0)}",
            "citations:",
        ]

        for c in citations:
            lines.extend(self._citation_yaml(c))

        return "\n".join(lines)

    def _citation_yaml(self, c: ContextCitation) -> list[str]:
        lines = [
            f"  - source_type: \"{c.source_type}\"",
            f"    id: \"{c.source_id}\"",
            f"    title: \"{self._escape_yaml(c.title)}\"",
            f"    confidence: {c.confidence}",
            f"    relevance: {c.relevance_score}",
        ]
        if c.content:
            lines.append(f"    content: \"{self._escape_yaml(c.content[:500])}\"")
        if c.reasons:
            reason_str = ", ".join(c.reasons)
            lines.append(f"    reasons: \"{self._escape_yaml(reason_str)}\"")
        if c.source_event_ids:
            lines.append(f"    source_events:")
            for eid in c.source_event_ids:
                lines.append(f"      - \"{eid}\"")
        return lines

    @staticmethod
    def _escape_yaml(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
