"""CanonicalKnowledgeRenderer — deterministic text rendering for knowledge nodes.

Every knowledge node is rendered to a canonical string that is:
  - Deterministic: same input always produces the same output.
  - Order-stable: fields appear in a fixed order, tags are sorted.
  - Normalized: whitespace and line endings are normalized.

The content_hash is computed from the canonical text and used for
incremental embedding rebuilds. If content hasn't changed, the hash
hasn't changed, and the embedding is reused.
"""
from __future__ import annotations

import hashlib


class CanonicalKnowledgeRenderer:
    """Deterministic rendering of knowledge nodes to canonical text.

    This is the single owner of canonicalization. All projections
    that need canonical text for knowledge nodes MUST use this class.
    """

    @staticmethod
    def render(
        node_id: str,
        title: str,
        content: str,
        knowledge_type: str = "",
        tags: list[str] | None = None,
        importance: str = "",
        domain: str = "",
    ) -> str:
        """Render a knowledge node to canonical text.

        The output is deterministic: same inputs always produce the same string.
        Fields are emitted in a fixed order. Tags are sorted alphabetically.
        """
        normalized_content = _normalize_whitespace(content)
        normalized_title = _normalize_whitespace(title)
        sorted_tags = ",".join(sorted(tags)) if tags else ""

        parts = [
            f"# {normalized_title}",
            f"type: {knowledge_type}",
            f"importance: {importance}",
            f"domain: {domain}",
            f"tags: {sorted_tags}",
            f"node_id: {node_id}",
            "",
            normalized_content,
        ]
        return "\n".join(parts)

    @staticmethod
    def content_hash(canonical_text: str) -> str:
        """Compute SHA256 hash of canonical text."""
        return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace: collapse runs of whitespace to single space,
    strip leading/trailing whitespace per line, normalize line endings."""
    lines = text.strip().splitlines()
    normalized = []
    for line in lines:
        collapsed = " ".join(line.split())
        normalized.append(collapsed)
    return "\n".join(normalized)
