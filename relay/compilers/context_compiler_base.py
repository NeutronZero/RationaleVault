"""Relay ContextPackageCompiler — Abstract base for agent-specific context compilation.

All ContextPackageCompiler implementations take a ContextPackage and produce
a CompilerOutput formatted for a specific agent's reasoning style.

Sibling abstraction to AgentCompiler (relay/compilers/base.py):
  - AgentCompiler: CognitiveHead → agent state context
  - ContextPackageCompiler: ContextPackage → agent retrieval context

Design principles:
  - Output-only. No LLM API calls. Relay is model-agnostic.
  - Deterministic: same ContextPackage → same CompilerOutput
  - Profile-aware: formatting adapts to the retrieval profile
  - All citations traceable to source events
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from relay.compilers.compiler_output import CompilerMetadata, CompilerOutput

if TYPE_CHECKING:
    from relay.knowledge.context_compiler import ContextPackage


class ContextPackageCompiler(ABC):
    """Abstract base class for ContextPackage → agent-specific context compilers.

    Each subclass renders a ContextPackage into a format optimized for
    a specific AI agent's context window, reasoning style, and prompt format.

    Subclasses must implement:
      - compile(package) → CompilerOutput
      - agent_name: str
      - format_name: str

    Optional overrides:
      - max_citations: int (default 30)
      - include_provenance: bool (default True)
      - metadata: CompilerMetadata (default auto-generated)
    """

    @abstractmethod
    def compile(self, package: ContextPackage) -> CompilerOutput:
        """Compile a ContextPackage into agent-specific formatted output.

        Args:
            package: The retrieval-blended context package.

        Returns:
            CompilerOutput with rendered content and metadata.
        """
        ...

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Human-readable name of the target agent (e.g. 'Claude')."""
        ...

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Output format name (e.g. 'markdown', 'yaml', 'json')."""
        ...

    @property
    def max_citations(self) -> int:
        """Maximum number of citations to include in output."""
        return 30

    @property
    def include_provenance(self) -> bool:
        """Whether to include source event traceability in output."""
        return True

    @property
    def metadata(self) -> CompilerMetadata:
        """Capability metadata for this compiler."""
        return CompilerMetadata(
            agent=self.agent_name,
            format_name=self.format_name,
            supports_provenance=self.include_provenance,
        )
