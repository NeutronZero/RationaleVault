"""Unit tests for the WriteFile skill."""
from __future__ import annotations

import os
import tempfile

import pytest

from rationalevault.skills import SkillInput
from ..skill import WriteFileSkill


def test_write_file_skill_success():
    """Verify the skill correctly writes a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "test.txt")
        content = "Hello, world!"
        
        skill = WriteFileSkill()
        input_data = SkillInput(
            metadata={
                "filepath": filepath,
                "content": content
            }
        )
        
        result = skill(input_data)
        
        assert result.status == "completed"
        assert result.metrics["bytes_written"] == len(content)
        
        with open(filepath, "r", encoding="utf-8") as f:
            assert f.read() == content


def test_write_file_skill_missing_inputs():
    """Verify the skill fails gracefully with missing inputs."""
    skill = WriteFileSkill()
    input_data = SkillInput(
        metadata={"filepath": "only_filepath.txt"}
    )
    result = skill(input_data)
    assert result.status == "failed"
    assert "Missing" in result.summary
