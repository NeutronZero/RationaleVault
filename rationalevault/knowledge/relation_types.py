from enum import Enum


class RelationType(str, Enum):
    """Ontology for knowledge graph relations.

    Used by KnowledgeRelation, KnowledgeEdge, and GraphEdge.
    Lives in its own module to avoid pulling the entire knowledge model stack.
    """

    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    DERIVED_FROM = "DERIVED_FROM"
    SUPERSEDES = "SUPERSEDES"
    RELATED_TO = "RELATED_TO"

    @classmethod
    def from_str(cls, value: str) -> "RelationType":
        """Parse a relation type from a string (case-insensitive).

        Single boundary adapter for CLI, MCP, JSON, and future imports.
        """
        return cls(value.upper())
