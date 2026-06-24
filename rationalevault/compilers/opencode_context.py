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

from rationalevault.compilers.compiler_output import CompilerOutput
from rationalevault.compilers.context_compiler_base import ContextPackageCompiler

if TYPE_CHECKING:
    from rationalevault.knowledge.context_compiler import ContextPackage
    from rationalevault.knowledge.context_types import ContextCitation
    from rationalevault.projections.continuation import ContinuationState


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
        ]
        if package.mode == "continuation" and package.continuation_state:
            sections.append(self._where_i_left_off(package.continuation_state))

        if package.graph_state and package.continuation_state:
            dep_ctx = self._dependency_context(package.graph_state, package.continuation_state)
            if dep_ctx:
                sections.append(dep_ctx)

        if package.knowledge_state:
            sections.append(self._knowledge_evolution(package.knowledge_state))

        sections.extend([
            self._goals(citations),
            self._decisions(citations),
            self._constraints(citations),
            self._recent_changes(citations),
            self._references(citations),
        ])

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

    def _where_i_left_off(self, state: ContinuationState) -> str:
        lines = [
            "## Where You Left Off",
            ""
        ]
        if state.last_session:
            ls = state.last_session
            lines.append(f"- **Last Session:** {ls.actor} at {ls.last_event_at} (session: {ls.session_id})")
        else:
            lines.append("- **Last Session:** unknown")
        
        if state.context_snapshots:
            latest = state.context_snapshots[-1]
            lines.append(f"- **Latest Snapshot:** {latest.get('summary', '')}")
            if latest.get("blocked_on"):
                lines.append(f"  - **Blocked on:** {latest['blocked_on']}")
            if latest.get("next_action"):
                lines.append(f"  - **Next action:** {latest['next_action']}")

        if state.in_progress_tasks:
            lines.append("- **In Progress Tasks:**")
            for t in state.in_progress_tasks:
                lines.append(f"  - [{t.priority}] {t.title}")

        if state.open_questions:
            lines.append("- **Open Questions:**")
            for q in state.open_questions:
                lines.append(f"  - [{q.priority}] {q.title}")

        if state.next_actions:
            lines.append("- **Next Actions:**")
            for idx, action in enumerate(state.next_actions, 1):
                lines.append(f"  {idx}. {action}")

        return "\n".join(lines)

    def _dependency_context(self, graph_state: Any, continuation_state: Any) -> str:
        """Dependency context for continuation — shows what breaks if work continues."""
        if not graph_state.nodes:
            return ""

        lines = [
            "### Dependency Context",
            ""
        ]

        tasks_shown = 0
        for task in continuation_state.in_progress_tasks[:3]:
            if tasks_shown >= 3:
                break

            matching_node = None
            if task.related_knowledge_ids:
                for kid in task.related_knowledge_ids:
                    if kid in graph_state.nodes:
                        matching_node = kid
                        break
            if not matching_node:
                matching_node = self._find_task_node(graph_state, task.title)

            if not matching_node:
                continue

            tasks_shown += 1

            try:
                chain = graph_state.dependency_chain(matching_node)
                if len(chain) > 1:
                    chain_labels = [n["node_id"] for n in chain]
                    lines.append(f"- **{task.title}**: {' → '.join(chain_labels)}")
                else:
                    lines.append(f"- **{task.title}**: no dependencies")
            except ValueError:
                lines.append(f"- **{task.title}**: cycle detected")

            impact = graph_state.impact_analysis(matching_node, depth=2)
            downstream_count = len(impact["downstream"])
            if downstream_count > 0:
                lines.append(f"  - Downstream: {downstream_count} affected")

            nearby = set(impact["affected_by_contradiction"]) & graph_state.conflicted_nodes
            if nearby:
                lines.append(f"  - Contradiction nearby: {len(nearby)} conflict(s)")

        if tasks_shown == 0:
            return ""

        return "\n".join(lines)

    @staticmethod
    def _find_task_node(graph_state: Any, task_title: str) -> str | None:
        """Find graph node matching task title (exact or contains)."""
        for nid, node in graph_state.nodes.items():
            if node.title.lower() == task_title.lower():
                return nid
        title_lower = task_title.lower()
        for nid, node in graph_state.nodes.items():
            if title_lower in node.title.lower() or node.title.lower() in title_lower:
                return nid
        return None

    def _knowledge_evolution(self, state: Any) -> str:
        """Generate Knowledge Evolution section from KnowledgeState."""
        lines = [
            "## Knowledge Evolution",
            ""
        ]

        health = state.health
        if health:
            lines.append(
                f"- Confidence: {health.confidence:.0%} | "
                f"Contradictions: {health.contradiction_rate:.0%} | "
                f"Invariants: {health.invariant_ratio:.0%}"
            )

        if state.invariants:
            lines.append("- **Invariants:**")
            for inv in state.invariants:
                marker = "declared" if inv.knowledge_type.value == "PROJECT_INVARIANT" else "emergent"
                lines.append(f"  - {inv.title} ({marker}, {inv.confidence.score:.0%})")

        if state.conflict_queue:
            lines.append("- **Requires Resolution:**")
            for conflict in state.conflict_queue:
                lines.append(f"  - {conflict.knowledge_a_title} vs {conflict.knowledge_b_title}")

        lines.append(f"- **Active:** {len(state.active_knowledge)} | **Validated:** {len(state.validated)} | **Proposed:** {len(state.proposed)}")

        return "\n".join(lines)

