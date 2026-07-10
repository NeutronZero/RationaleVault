"""Skill Scaffolder."""
from pathlib import Path

from rationalevault.cli.scaffolders.engine import render_scaffold


def scaffold_skill(name: str, dest: Path) -> None:
    """Scaffold a new skill."""
    pascal_name = "".join(word.capitalize() for word in name.split("_"))
    
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    template_dir = project_root / "examples" / "skill_example"
    
    substitutions = {
        "WriteFileSkill": pascal_name,
        "WriteFile": pascal_name,
        "write_file_skill": name.lower(),
        "write_file": name.lower()
    }
    
    render_scaffold(template_dir, dest, substitutions, is_projection=False)
    
    init_file = dest / "__init__.py"
    if init_file.exists():
        content = init_file.read_text(encoding="utf-8")
        metadata = f"\n\nSKILL_NAME = \"{name.lower()}\"\nSCHEMA_VERSION = 1\nSKILL_VERSION = 1\nTEMPLATE_VERSION = 1\n"
        init_file.write_text(content + metadata, encoding="utf-8")
