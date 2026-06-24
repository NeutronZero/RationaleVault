"""RationaleVault Organization Relation Types — Ontology for organizational graph edges.

Separate from knowledge-level RelationType to avoid cross-contamination.
"""
from enum import Enum


class OrganizationRelationType(str, Enum):
    """Ontology for organizational graph relations.

    TRANSFERRED_TO: Knowledge was transferred from project A to project B.
    SHARED_BY: Projects share common knowledge objects.
    CONFLICTS_WITH: Projects have contradictory knowledge.
    IN_CLUSTER: Projects are in the same cluster (Jaccard similarity).
    DERIVES_FROM: Project lineage (reserved — requires explicit project-lineage metadata).
    """

    TRANSFERRED_TO = "TRANSFERRED_TO"
    SHARED_BY = "SHARED_BY"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    IN_CLUSTER = "IN_CLUSTER"
    DERIVES_FROM = "DERIVES_FROM"

    @classmethod
    def from_str(cls, value: str) -> "OrganizationRelationType":
        """Parse an organization relation type from a string (case-insensitive)."""
        return cls(value.upper())
