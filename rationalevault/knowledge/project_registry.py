"""RationaleVault Project Registry — Cross-project discovery.

Manages a registry of known projects at ~/.rationalevault/registry.yaml.
Provides deterministic project discovery for CrossProjectProjection.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


REGISTRY_DIR = Path.home() / ".rationalevault"
REGISTRY_FILE = REGISTRY_DIR / "registry.yaml"


@dataclass
class ProjectEntry:
    """A registered project."""
    id: str
    name: str
    path: str
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: list[str] = field(default_factory=list)


@dataclass
class ProjectRegistry:
    """Registry of known projects.

    Stored at ~/.rationalevault/registry.yaml.
    Provides deterministic project discovery for cross-project queries.
    """
    projects: list[ProjectEntry] = field(default_factory=list)

    @classmethod
    def load(cls) -> "ProjectRegistry":
        """Load registry from disk. Returns empty registry if file missing."""
        if not REGISTRY_FILE.exists():
            return cls()
        try:
            import yaml
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            projects = [
                ProjectEntry(
                    id=p["id"],
                    name=p.get("name", ""),
                    path=p["path"],
                    registered_at=p.get("registered_at", ""),
                    tags=p.get("tags", []),
                )
                for p in data.get("projects", [])
            ]
            return cls(projects=projects)
        except Exception:
            return cls()

    def save(self) -> None:
        """Save registry to disk."""
        import os
        import time
        from contextlib import contextmanager
        import yaml

        LOCK_DIR = REGISTRY_FILE.with_suffix(".lockdir")

        @contextmanager
        def file_lock(timeout: float = 5.0, delay: float = 0.05):
            start_time = time.time()
            while True:
                try:
                    os.mkdir(LOCK_DIR)
                    break
                except FileExistsError:
                    if time.time() - start_time > timeout:
                        try:
                            mtime = os.path.getmtime(LOCK_DIR)
                            if time.time() - mtime > 10.0:
                                os.rmdir(LOCK_DIR)
                                continue
                        except Exception:
                            pass
                        raise TimeoutError(f"Could not acquire write lock on registry within {timeout}s")
                    time.sleep(delay)
            try:
                yield
            finally:
                try:
                    os.rmdir(LOCK_DIR)
                except Exception:
                    pass

        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "path": p.path,
                    "registered_at": p.registered_at,
                    "tags": p.tags,
                }
                for p in self.projects
            ]
        }
        with file_lock():
            with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def register(self, project_path: str) -> ProjectEntry:
        """Register a project by its filesystem path.

        Raises ValueError if project already registered or path invalid.
        """
        resolved = Path(project_path).resolve()
        if not resolved.exists():
            raise ValueError(f"Path does not exist: {resolved}")

        # Check if already registered
        for entry in self.projects:
            if Path(entry.path).resolve() == resolved:
                raise ValueError(f"Project already registered: {entry.id}")

        # Generate collision-resistant ID from canonical path
        project_id = hashlib.sha256(str(resolved).encode()).hexdigest()[:12]

        entry = ProjectEntry(
            id=project_id,
            name=resolved.name,
            path=str(resolved),
        )
        self.projects.append(entry)
        self.save()
        return entry

    def unregister(self, project_id: str) -> bool:
        """Remove a project from the registry. Returns True if found."""
        before = len(self.projects)
        self.projects = [p for p in self.projects if p.id != project_id]
        if len(self.projects) < before:
            self.save()
            return True
        return False

    def get_entry(self, project_id: str) -> Optional[ProjectEntry]:
        """Look up a project by ID."""
        for entry in self.projects:
            if entry.id == project_id:
                return entry
        return None

    def find_by_tag(self, tag: str) -> list[ProjectEntry]:
        """Find projects with a specific tag."""
        return [p for p in self.projects if tag in p.tags]

    def list_projects(self) -> list[ProjectEntry]:
        """Return all registered projects."""
        return list(self.projects)
