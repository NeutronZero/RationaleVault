"""Tests for ProjectRegistry and CLI project commands."""
from __future__ import annotations

from pathlib import Path

import pytest

from rationalevault.knowledge.project_registry import (
    ProjectEntry,
    ProjectRegistry,
)


class TestProjectRegistry:
    @pytest.fixture(autouse=True)
    def isolated_registry(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rationalevault.knowledge.project_registry.REGISTRY_FILE",
            tmp_path / "registry.yaml",
        )
        monkeypatch.setattr(
            "rationalevault.knowledge.project_registry.REGISTRY_DIR",
            tmp_path,
        )

    def test_load_empty(self) -> None:
        registry = ProjectRegistry.load()
        assert registry.projects == []

    def test_register_and_list(self, tmp_path: Path) -> None:
        registry = ProjectRegistry.load()
        entry = registry.register(str(tmp_path))

        # ID is now SHA-256 of canonical path (12 hex chars), not directory name
        assert len(entry.id) == 12
        assert all(c in "0123456789abcdef" for c in entry.id)
        assert entry.name == tmp_path.name
        assert entry.path == str(tmp_path)

        loaded = ProjectRegistry.load()
        assert len(loaded.projects) == 1
        assert loaded.projects[0].id == entry.id

    def test_unregister(self, tmp_path: Path) -> None:
        registry = ProjectRegistry.load()
        entry = registry.register(str(tmp_path))
        assert registry.unregister(entry.id) is True
        assert len(registry.projects) == 0

    def test_unregister_nonexistent(self) -> None:
        registry = ProjectRegistry.load()
        assert registry.unregister("nonexistent") is False

    def test_get_entry(self, tmp_path: Path) -> None:
        registry = ProjectRegistry.load()
        entry = registry.register(str(tmp_path))
        found = registry.get_entry(entry.id)
        assert found is not None
        assert found.id == entry.id

    def test_get_entry_not_found(self) -> None:
        registry = ProjectRegistry.load()
        assert registry.get_entry("nonexistent") is None

    def test_register_duplicate_raises(self, tmp_path: Path) -> None:
        registry = ProjectRegistry.load()
        registry.register(str(tmp_path))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(str(tmp_path))

    def test_register_nonexistent_path_raises(self) -> None:
        registry = ProjectRegistry.load()
        with pytest.raises(ValueError, match="does not exist"):
            registry.register("/nonexistent/path")

    def test_find_by_tag(self, tmp_path: Path) -> None:
        registry = ProjectRegistry.load()
        entry = registry.register(str(tmp_path))
        entry.tags.append("architecture")
        registry.save()

        found = registry.find_by_tag("architecture")
        assert len(found) == 1
        assert found[0].id == entry.id

    def test_find_by_tag_empty(self) -> None:
        registry = ProjectRegistry.load()
        assert registry.find_by_tag("nonexistent") == []

    def test_deterministic(self, tmp_path: Path) -> None:
        registry1 = ProjectRegistry.load()
        registry1.register(str(tmp_path))

        registry2 = ProjectRegistry.load()
        assert len(registry2.projects) == 1
        assert registry2.projects[0].id == registry1.projects[0].id
