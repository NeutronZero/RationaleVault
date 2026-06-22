"""Relay Compiler Registry — Lazy singleton registry for ContextPackageCompilers.

Provides agent name → compiler instance mapping. Uses lazy initialization
so compilers are only instantiated when first requested.

Usage:
    from relay.compilers.registry import get_context_compiler, available_agents

    compiler = get_context_compiler("claude")
    output = compiler.compile(package)

    agents = available_agents()  # ["claude", "opencode", "cursor"]
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from relay.compilers.context_compiler_base import ContextPackageCompiler


_REGISTRY: dict[str, type[ContextPackageCompiler]] = {}
_INSTANCES: dict[str, ContextPackageCompiler] = {}


def _lazy_import(agent: str) -> type[ContextPackageCompiler]:
    """Lazy import to avoid circular dependencies and startup cost."""
    if agent in _REGISTRY:
        return _REGISTRY[agent]

    if agent == "claude":
        from relay.compilers.claude_context import ClaudeContextCompiler
        _REGISTRY["claude"] = ClaudeContextCompiler
    elif agent == "opencode":
        from relay.compilers.opencode_context import OpenCodeContextCompiler
        _REGISTRY["opencode"] = OpenCodeContextCompiler
    elif agent == "cursor":
        from relay.compilers.cursor_context import CursorContextCompiler
        _REGISTRY["cursor"] = CursorContextCompiler
    else:
        raise ValueError(
            f"Unknown agent: {agent!r}. "
            f"Available agents: {', '.join(available_agents())}"
        )

    return _REGISTRY[agent]


def get_context_compiler(agent: str) -> ContextPackageCompiler:
    """Get a ContextPackageCompiler instance for the given agent.

    Returns a lazy singleton — first call creates the instance,
    subsequent calls return the cached instance.

    Args:
        agent: Agent name ("claude", "opencode", "cursor")

    Returns:
        ContextPackageCompiler instance

    Raises:
        ValueError: If agent is not registered
    """
    if agent not in _INSTANCES:
        cls = _lazy_import(agent)
        _INSTANCES[agent] = cls()

    return _INSTANCES[agent]


def available_agents() -> list[str]:
    """Return list of all registered agent names."""
    return ["claude", "opencode", "cursor"]


def reset_registry() -> None:
    """Reset the registry. Primarily for testing."""
    _REGISTRY.clear()
    _INSTANCES.clear()
