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
        ]

        if package.mode == "continuation" and package.continuation_state:
            state = package.continuation_state
            lines.append("continuation:")
            if state.last_session:
                ls = state.last_session
                lines.append("  last_session:")
                lines.append(f"    session_id: \"{ls.session_id}\"")
                lines.append(f"    actor: \"{self._escape_yaml(ls.actor)}\"")
                lines.append(f"    last_event_at: \"{ls.last_event_at}\"")
            else:
                lines.append("  last_session: null")

            if state.context_snapshots:
                latest = state.context_snapshots[-1]
                lines.append("  latest_snapshot:")
                lines.append(f"    summary: \"{self._escape_yaml(latest.get('summary', ''))}\"")
                if latest.get("blocked_on"):
                    lines.append(f"    blocked_on: \"{self._escape_yaml(latest['blocked_on'])}\"")
                if latest.get("next_action"):
                    lines.append(f"    next_action: \"{self._escape_yaml(latest['next_action'])}\"")
            else:
                lines.append("  latest_snapshot: null")

            if state.in_progress_tasks:
                lines.append("  in_progress_tasks:")
                for t in state.in_progress_tasks:
                    lines.append(f"    - task_id: \"{t.task_id}\"")
                    lines.append(f"      title: \"{self._escape_yaml(t.title)}\"")
                    lines.append(f"      priority: \"{t.priority}\"")
                    if t.progress_notes:
                        lines.append("      progress_notes:")
                        for n in t.progress_notes:
                            lines.append(f"        - \"{self._escape_yaml(n.get('note', ''))}\"")
            else:
                lines.append("  in_progress_tasks: []")

            if state.open_questions:
                lines.append("  open_questions:")
                for q in state.open_questions:
                    lines.append(f"    - question_id: \"{q.question_id}\"")
                    lines.append(f"      title: \"{self._escape_yaml(q.title)}\"")
                    lines.append(f"      priority: \"{q.priority}\"")
            else:
                lines.append("  open_questions: []")

            if state.next_actions:
                lines.append("  next_actions:")
                for a in state.next_actions:
                    lines.append(f"    - \"{self._escape_yaml(a)}\"")
            else:
                lines.append("  next_actions: []")

            # Dependency context
            if package.graph_state:
                dep_lines = self._dependency_context_yaml(package.graph_state, state)
                if dep_lines:
                    lines.extend(dep_lines)

        if package.knowledge_state:
            ks = package.knowledge_state
            lines.append("knowledge_evolution:")
            if ks.health:
                lines.append("  health:")
                lines.append(f"    confidence: {ks.health.confidence:.4f}")
                lines.append(f"    contradiction_rate: {ks.health.contradiction_rate:.4f}")
                lines.append(f"    invariant_ratio: {ks.health.invariant_ratio:.4f}")
                lines.append(f"    overall: {ks.health.overall:.4f}")

            if ks.invariants:
                lines.append("  invariants:")
                for inv in ks.invariants:
                    marker = "declared" if inv.knowledge_type.value == "PROJECT_INVARIANT" else "emergent"
                    lines.append(f"    - title: \"{self._escape_yaml(inv.title)}\"")
                    lines.append(f"      type: \"{marker}\"")
                    lines.append(f"      confidence: {inv.confidence.score:.4f}")

            if ks.conflict_queue:
                lines.append("  conflict_queue:")
                for c in ks.conflict_queue:
                    lines.append(f"    - a: \"{self._escape_yaml(c.knowledge_a_title)}\"")
                    lines.append(f"      b: \"{self._escape_yaml(c.knowledge_b_title)}\"")
                    lines.append(f"      confidence: {c.confidence}")

            lines.append("  active_count: %d" % len(ks.active_knowledge))
            lines.append("  validated_count: %d" % len(ks.validated))
            lines.append("  proposed_count: %d" % len(ks.proposed))

        lines.extend([
            f"source_counts:",
            f"  events: {package.source_counts.get('events', 0)}",
            f"  memories: {package.source_counts.get('memories', 0)}",
            f"  knowledge: {package.source_counts.get('knowledge', 0)}",
            "citations:",
        ])

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

    def _dependency_context_yaml(self, graph_state: Any, continuation_state: Any) -> list[str]:
        """Dependency context in YAML format."""
        if not graph_state.nodes:
            return []

        lines = ["  dependency_context:"]

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
            lines.append(f"    - task: \"{self._escape_yaml(task.title)}\"")

            try:
                chain = graph_state.dependency_chain(matching_node)
                if len(chain) > 1:
                    chain_labels = [n["node_id"] for n in chain]
                    lines.append(f"      chain: \"{' → '.join(chain_labels)}\"")
                else:
                    lines.append(f"      chain: \"no dependencies\"")
            except ValueError:
                lines.append(f"      chain: \"cycle detected\"")

            impact = graph_state.impact_analysis(matching_node, depth=2)
            downstream_count = len(impact["downstream"])
            if downstream_count > 0:
                lines.append(f"      downstream_affected: {downstream_count}")

            nearby = set(impact["affected_by_contradiction"]) & graph_state.conflicted_nodes
            if nearby:
                lines.append(f"      contradiction_nearby: {len(nearby)}")

        if tasks_shown == 0:
            return []

        return lines

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
