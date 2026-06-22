from __future__ import annotations

from pathlib import Path
from rationalevault.memory.base import BaseMemoryProvider
from rationalevault.memory.markdown_provider import MarkdownMemoryProvider
from rationalevault.memory.sqlite_provider import SQLiteMemoryProvider

try:
    import yaml
except ImportError:
    yaml = None


def get_memory_provider() -> BaseMemoryProvider:
    """
    Resolves the configured Memory Provider from project.yaml.
    Defaults to MarkdownMemoryProvider inside .rationalevault/memory.md.
    """
    project_root = Path.cwd()
    project_yaml = project_root / ".rationalevault" / "project.yaml"

    if project_yaml.exists() and yaml:
        try:
            with open(project_yaml, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            mem_config = config.get("memory", {})
            provider = mem_config.get("provider", "markdown").lower()
            path = mem_config.get("path")

            if provider == "sqlite":
                return SQLiteMemoryProvider(db_path=path)
            elif provider == "markdown":
                return MarkdownMemoryProvider(file_path=path)
        except Exception:
            pass

    return MarkdownMemoryProvider()
