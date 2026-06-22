"""RationaleVault Knowledge Store Factory — Resolves the configured Knowledge Provider."""
from __future__ import annotations

from pathlib import Path

from rationalevault.knowledge.store import BaseKnowledgeProvider, MarkdownKnowledgeProvider, SQLiteKnowledgeProvider

try:
    import yaml
except ImportError:
    yaml = None


def get_knowledge_provider() -> BaseKnowledgeProvider:
    """
    Resolves the configured Knowledge Provider from project.yaml.
    Defaults to MarkdownKnowledgeProvider inside .rationalevault/knowledge.md.
    """
    project_root = Path.cwd()
    project_yaml = project_root / ".rationalevault" / "project.yaml"

    if project_yaml.exists() and yaml:
        try:
            with open(project_yaml, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            knowledge_config = config.get("knowledge", {})
            provider = knowledge_config.get("provider", "markdown").lower()
            path = knowledge_config.get("path")

            if provider == "sqlite":
                return SQLiteKnowledgeProvider(db_path=path)
            elif provider == "markdown":
                return MarkdownKnowledgeProvider(file_path=path)
        except Exception:
            pass

    return MarkdownKnowledgeProvider()
