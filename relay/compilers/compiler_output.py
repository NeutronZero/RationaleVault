"""Relay Compiler Output — Structured output from ContextPackageCompiler.

CompilerOutput is the return type of all ContextPackageCompiler implementations.
It carries both the rendered content and metadata needed for evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompilerMetadata:
    """Capability metadata for a ContextPackageCompiler.

    Used by the registry to describe what each agent supports.
    """
    agent: str
    format_name: str
    supports_provenance: bool = True
    supports_hierarchical_sections: bool = True
    max_context_size: int = 100_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "format_name": self.format_name,
            "supports_provenance": self.supports_provenance,
            "supports_hierarchical_sections": self.supports_hierarchical_sections,
            "max_context_size": self.max_context_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompilerMetadata:
        return cls(
            agent=data["agent"],
            format_name=data["format_name"],
            supports_provenance=data.get("supports_provenance", True),
            supports_hierarchical_sections=data.get("supports_hierarchical_sections", True),
            max_context_size=data.get("max_context_size", 100_000),
        )


@dataclass
class CompilerOutput:
    """Structured output from a ContextPackageCompiler.

    Carries rendered content plus metadata for evaluation.
    All fields are serializable for benchmark artifact storage.
    """
    query: str
    profile: str
    agent: str
    format_name: str
    rendered_content: str
    citation_count: int
    source_counts: dict[str, int]
    compile_time_ms: float
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "profile": self.profile,
            "agent": self.agent,
            "format_name": self.format_name,
            "rendered_content": self.rendered_content,
            "citation_count": self.citation_count,
            "source_counts": self.source_counts,
            "compile_time_ms": self.compile_time_ms,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompilerOutput:
        return cls(
            query=data["query"],
            profile=data["profile"],
            agent=data["agent"],
            format_name=data["format_name"],
            rendered_content=data["rendered_content"],
            citation_count=data["citation_count"],
            source_counts=data["source_counts"],
            compile_time_ms=data["compile_time_ms"],
            generated_at=data["generated_at"],
        )
