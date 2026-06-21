"""
Relay Agent Compiler Interface.

All agent-specific compilers implement AgentCompiler.

Design:
  - Compilers are output-only. They do not call any LLM API.
  - Relay is model-agnostic. Context blocks are injected by the user.
  - compile(head) → str is the only required method.
  - The output format is entirely up to the compiler for the target agent.

Available compilers:
  ClaudeCompiler  — relay/compilers/claude.py
  (future) CursorCompiler, HermesCompiler, ChatGPTCompiler, OpenCodeCompiler
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from relay.cognitive_head.compiler import CognitiveHead


class AgentCompiler(ABC):
    """
    Abstract base class for all Relay agent context compilers.

    Each subclass is responsible for translating a CognitiveHead into
    a formatted string that is optimal for a specific AI agent's
    reasoning style, context window, and prompt format.
    """

    @abstractmethod
    def compile(self, head: CognitiveHead) -> str:
        """
        Compile a CognitiveHead into a formatted context string.

        The output is intended to be pasted at the start of an agent
        conversation to enable immediate productive resumption.

        Args:
            head: The compiled project state from compile_cognitive_head().

        Returns:
            A formatted string ready for the target agent.
        """
        ...

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Human-readable name of the target agent (e.g. 'Claude')."""
        ...
