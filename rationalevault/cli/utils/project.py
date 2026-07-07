import uuid
from pathlib import Path

def _resolve_project_id() -> uuid.UUID:
    """Helper to resolve project ID from project.yaml in the current workspace."""
    project_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    project_yaml = Path.cwd() / ".rationalevault" / "project.yaml"
    if project_yaml.exists():
        try:
            import yaml
            with open(project_yaml, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            project_id = uuid.UUID(config.get("project_id", str(project_id)))
        except Exception as e:
            import sys
            sys.stderr.write(f"Warning: Failed to parse project.yaml at {project_yaml}: {e}\n")
    return project_id
