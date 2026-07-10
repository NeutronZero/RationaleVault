"""
Tests for Scaffolders (Generators).

Verifies that the generated templates are valid, importable, and pass their own tests.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

from rationalevault.cli.scaffolders.projection import scaffold_projection
from rationalevault.cli.scaffolders.skill import scaffold_skill
from rationalevault.cli.scaffolders.validator import validate_projection


def test_projection_scaffolder_full_lifecycle():
    """Generate a projection, validate it, and run its tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        dest = Path(temp_dir) / "my_custom_projection"
        
        # 1. Generate
        scaffold_projection(name="my_custom_projection", dest=dest, with_runtime=True)
        
        # 2. Validate using doctor
        is_valid = validate_projection(str(dest))
        assert is_valid, "Doctor validation failed on generated projection"
        
        # 3. Import
        # Add the temp directory to sys.path so we can import the generated module
        sys.path.insert(0, str(dest.parent))
        try:
            import my_custom_projection
            assert my_custom_projection.PROJECTION_NAME == "my_custom_projection"
            assert my_custom_projection.SCHEMA_VERSION == 1
        finally:
            # Clean up sys.path
            sys.path.pop(0)
            
        # 4. Run Pytest on the generated directory
        # We need to run pytest in-process, but since it's a test itself,
        # it might be tricky. Let's just use subprocess to ensure isolation.
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-n", "0", str(dest / "tests")],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Generated projection tests failed:\n{result.stdout}\n{result.stderr}"


def test_skill_scaffolder_full_lifecycle():
    """Generate a skill, validate it, and run its tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        dest = Path(temp_dir) / "my_custom_skill"
        
        # 1. Generate
        scaffold_skill(name="my_custom_skill", dest=dest)
        
        # 2. Import
        sys.path.insert(0, str(dest.parent))
        try:
            import my_custom_skill
            assert my_custom_skill.SKILL_NAME == "my_custom_skill"
        finally:
            sys.path.pop(0)
            
        # 3. Run Pytest
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-n", "0", str(dest / "tests")],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Generated skill tests failed:\n{result.stdout}\n{result.stderr}"
