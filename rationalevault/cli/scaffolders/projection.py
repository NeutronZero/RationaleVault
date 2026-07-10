"""Projection Scaffolder."""
from pathlib import Path

from rationalevault.cli.scaffolders.engine import render_scaffold


def scaffold_projection(name: str, dest: Path, with_cli: bool = False, with_mcp: bool = False, with_runtime: bool = False) -> None:
    """Scaffold a new projection."""
    # Convert name like my_projection to MyProjection
    pascal_name = "".join(word.capitalize() for word in name.split("_"))
    
    # Locate the examples directory relative to this file
    # We are in rationalevault/cli/scaffolders/projection.py
    # examples is at the root of the project
    # So we go up 3 levels to rationalevault, then up 1 level to root, then down to examples
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    template_dir = project_root / "examples" / "projection_example"
    
    substitutions = {
        "TaskTracker": pascal_name,
        "task_tracker": name.lower(),
        "Task Tracker": name.replace("_", " ").title(),
        "task-tracker": name.lower().replace("_", "-")
    }
    
    render_scaffold(template_dir, dest, substitutions, is_projection=True)
    
    # Optionally remove runtime.py if not requested
    if not with_runtime:
        runtime_file = dest / "runtime.py"
        if runtime_file.exists():
            runtime_file.unlink()
            
    # Metadata injection is handled by the engine's header injection, 
    # but we also need to modify projection.py to add PROJECTION_NAME = ...
    # Wait, it's better if we just let the generator replace the strings.
    # The template (example) has __init__.py and other files where things can be defined.
    # We will inject the metadata constants into __init__.py of the generated code.
    
    init_file = dest / "__init__.py"
    if init_file.exists():
        content = init_file.read_text(encoding="utf-8")
        metadata = f"\n\nPROJECTION_NAME = \"{name.lower()}\"\nSCHEMA_VERSION = 1\nPROJECTION_VERSION = 1\nTEMPLATE_VERSION = 1\n"
        init_file.write_text(content + metadata, encoding="utf-8")
