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
    from rationalevault.projections.continuation import ContinuationState
    from rationalevault.organization.continuation import (
        OrganizationContinuationState,
    )

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
    "continuation": "🔁",
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
        ]
        if package.mode == "continuation" and package.continuation_state:
            sections.append(self._where_i_left_off(package.continuation_state))

        if package.graph_state and package.continuation_state:
            dep_ctx = self._dependency_context(package.graph_state, package.continuation_state)
            if dep_ctx:
                sections.append(dep_ctx)

        if package.organization_continuation_state:
            sections.append(
                self._where_the_organization_left_off(
                    package.organization_continuation_state,
                )
            )

        if package.recommendations:
            sections.append(self._recommended_actions(package.recommendations))

        if package.knowledge_state:
            sections.append(self._knowledge_evolution(package.knowledge_state))

        sections.extend([
            self._critical_constraints(citations),
            self._decisions_and_rationale(citations),
            self._architecture_and_design(citations),
            self._recent_activity(citations),
            self._relevant_memories(citations),
            self._source_traceability(citations) if self.include_provenance else "",
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

    def _where_i_left_off(self, state: ContinuationState) -> str:
        lines = [
            "## 🔁 Where You Left Off",
            ""
        ]
        if state.last_session:
            ls = state.last_session
            lines.append(f"> Last session: {ls.actor} | {ls.last_event_at} (session {ls.session_id})")
        else:
            lines.append("> Last session: unknown")

        lines.append("")

        if state.context_snapshots:
            latest = state.context_snapshots[-1]
            lines.append("### Latest Context Snapshot")
            lines.append(f"**Summary:** {latest.get('summary', '')}")
            if latest.get("blocked_on"):
                lines.append(f"**Blocked on:** {latest['blocked_on']}")
            if latest.get("next_action"):
                lines.append(f"**Next action:** {latest['next_action']}")
            lines.append("")

        if state.in_progress_tasks:
            lines.append("### In Progress")
            for t in state.in_progress_tasks:
                priority_label = f"[{t.priority.upper()}]" if t.priority else ""
                lines.append(f"- ◑ {priority_label} {t.title}")
                for note_dict in t.progress_notes:
                    lines.append(f"  └ {note_dict.get('note', '')}")
            lines.append("")

        if state.open_questions:
            lines.append("### Open Questions — Resolve First")
            for q in state.open_questions:
                priority_label = f"[{q.priority.upper()}]" if q.priority else ""
                lines.append(f"- ⚠️ {priority_label} {q.title}")
            lines.append("")

        if state.next_actions:
            lines.append("### Next Actions")
            for idx, action in enumerate(state.next_actions, 1):
                lines.append(f"{idx}. {action}")
            lines.append("")

        lines.append("---")
        lines.append("Do not re-derive information present above.")
        lines.append("Record events back to RationaleVault when work completes.")
        return "\n".join(lines)

    def _where_the_organization_left_off(
        self,
        state: OrganizationContinuationState,
    ) -> str:
        """Organization-level continuation context."""
        lines = [
            "## 🏢 Where the Organization Left Off",
            ""
        ]

        health = state.health
        lines.append(
            f"> Organizational health: {health.overall:.0%} | "
            f"Activity coverage: {health.activity_coverage:.0%} | "
            f"Continuity: {health.continuity:.0%}"
        )
        lines.append("")

        if state.projects_needing_attention:
            lines.append("### Projects Needing Attention")
            for pid in state.projects_needing_attention:
                lines.append(f"- ⚠️ {pid}")
            lines.append("")

        if state.organizational_next_actions:
            lines.append("### Organizational Next Actions")
            for idx, action in enumerate(state.organizational_next_actions, 1):
                lines.append(f"{idx}. {action}")
            lines.append("")

        if state.continuation_summary:
            lines.append("### Summary")
            for item in state.continuation_summary:
                lines.append(f"- {item}")
            lines.append("")

        lines.append("---")
        lines.append(
            "Review organization-wide state before cross-project work."
        )
        return "\n".join(lines)

    def _recommended_actions(self, recommendations: Any) -> str:
        """Render recommended actions from the recommendation engine."""
        from rationalevault.recommendations.models import RecommendationSet

        if not isinstance(recommendations, RecommendationSet):
            return ""

        MAX_RECOMMENDED_ACTIONS = 10
        recs = recommendations.recommendations[:MAX_RECOMMENDED_ACTIONS]
        if not recs:
            return ""

        lines = [
            "## Recommended Actions",
            ""
        ]

        for idx, rec in enumerate(recs, 1):
            priority_label = f"[P{rec.priority}]"
            lines.append(f"{idx}. {priority_label} **{rec.title}**")
            for note in rec.rationale[:2]:
                lines.append(f"   └ {note}")
            if rec.affected_projects:
                proj_str = ", ".join(rec.affected_projects)
                lines.append(f"   └ Projects: {proj_str}")
            lines.append("")

        load = recommendations.attention_load
        if load > 0:
            lines.append(f"> Attention load: {load:.0%} of categories active")
        lines.append("")

        lines.append("---")
        lines.append("Review and address recommendations before cross-project work.")

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

            # Try related_knowledge_ids first, fall back to title matching
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

            # Dependency chain
            try:
                chain = graph_state.dependency_chain(matching_node)
                if len(chain) > 1:
                    chain_labels = [n["node_id"] for n in chain]
                    lines.append(f"**{task.title}** chain: {' → '.join(chain_labels)}")
                else:
                    lines.append(f"**{task.title}**: no dependencies")
            except ValueError:
                lines.append(f"**{task.title}**: cycle detected in dependency chain")

            # Impact analysis
            impact = graph_state.impact_analysis(matching_node, depth=2)
            downstream_count = len(impact["downstream"])
            upstream_count = len(impact["upstream"])
            if downstream_count > 0 or upstream_count > 0:
                parts = []
                if downstream_count > 0:
                    parts.append(f"{downstream_count} downstream")
                if upstream_count > 0:
                    parts.append(f"{upstream_count} upstream")
                lines.append(f"  Affected: {', '.join(parts)}")

            # Nearby contradictions
            nearby = set(impact["affected_by_contradiction"]) & graph_state.conflicted_nodes
            if nearby:
                lines.append(f"  ⚠ Contradiction nearby: {len(nearby)} conflict(s)")

            lines.append("")

        if tasks_shown == 0:
            return ""

        return "\n".join(lines)

    @staticmethod
    def _find_task_node(graph_state: Any, task_title: str) -> str | None:
        """Find graph node matching task title (exact or contains)."""
        # Exact match
        for nid, node in graph_state.nodes.items():
            if node.title.lower() == task_title.lower():
                return nid
        # Contains match
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

        # Health snapshot
        health = state.health
        if health:
            lines.append(
                f"Confidence: {health.confidence:.0%} | "
                f"Contradictions: {health.contradiction_rate:.0%} | "
                f"Invariants: {health.invariant_ratio:.0%}"
            )
            lines.append("")

        # Invariants
        if state.invariants:
            lines.append("### Invariants (must not be violated)")
            lines.append("")
            for inv in state.invariants:
                marker = "declared" if inv.knowledge_type.value == "PROJECT_INVARIANT" else "emergent"
                lines.append(f"- **{inv.title}** ({marker}, {inv.confidence.score:.0%})")
            lines.append("")

        # Conflict queue
        if state.conflict_queue:
            lines.append("### Requires Resolution")
            lines.append("")
            for conflict in state.conflict_queue:
                lines.append(
                    f"- ⚠️ **{conflict.knowledge_a_title}** vs "
                    f"**{conflict.knowledge_b_title}**"
                )
            lines.append("")

        # Active knowledge summary
        lines.append("### Knowledge State")
        lines.append("")
        lines.append(f"- Active: {len(state.active_knowledge)}")
        lines.append(f"- Validated: {len(state.validated)}")
        lines.append(f"- Proposed: {len(state.proposed)}")
        lines.append(f"- Stale: {len(state.stale_knowledge)}")

        return "\n".join(lines)

