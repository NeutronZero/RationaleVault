"""
Adapter Generator — compiles agent-specific instructions/rules from relay_protocol.yaml and RELAY_SKILL.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yaml
except ImportError:
    print("Warning: PyYAML not installed. Fallback to basic string parsing for YAML.")
    yaml = None


def load_protocol(protocol_path: Path) -> dict:
    if not protocol_path.exists():
        return {}
    
    content = protocol_path.read_text(encoding="utf-8")
    if yaml:
        return yaml.safe_load(content)
    
    # Simple fallback parser if PyYAML is not installed
    protocol = {"rules": [], "execution_priority": []}
    current_rule = {}
    for line in content.splitlines():
        line_strip = line.strip()
        if line_strip.startswith("name:"):
            protocol["name"] = line_strip.split(":", 1)[1].strip().replace('"', '')
        elif line_strip.startswith("-") and "resolve_questions_first" in line:
            protocol["rules"].append({"id": "resolve_questions_first"})
        elif line_strip.startswith("-") and "respect_accepted_decisions" in line:
            protocol["rules"].append({"id": "respect_accepted_decisions"})
        elif line_strip.startswith("-") and "emit_candidate_events" in line:
            protocol["rules"].append({"id": "emit_candidate_events"})
        elif line_strip.startswith("-") and "continue_from_current_focus" in line:
            protocol["rules"].append({"id": "continue_from_current_focus"})
    return protocol


def main() -> None:
    project_root = Path(__file__).parent.parent
    relay_dir = project_root / ".relay"
    protocol_path = relay_dir / "relay_protocol.yaml"
    skill_path = relay_dir / "RELAY_SKILL.md"
    adapters_dir = relay_dir / "adapters"

    if not protocol_path.exists() or not skill_path.exists():
        print("Error: relay_protocol.yaml or RELAY_SKILL.md is missing in .relay/")
        sys.exit(1)

    protocol = load_protocol(protocol_path)
    skill_text = skill_path.read_text(encoding="utf-8")

    # Generate agent directories
    for agent in ["claude", "cursor", "copilot", "opencode"]:
        (adapters_dir / agent).mkdir(parents=True, exist_ok=True)

    # 1. Claude Adapter (CLAUDE.md)
    claude_adapter = (
        f"# Claude Code Instruction Adapter\n"
        f"Generated from Relay Protocol config.\n\n"
        f"{skill_text}\n\n"
        f"## Claude Code Specific constraints:\n"
        f"- Always scan files for `### RELAY_EVENT_CANDIDATES` on completion.\n"
        f"- Strictly run test command `pytest tests/unit/` before handoff to ensure correctness.\n"
    )
    (adapters_dir / "claude" / "CLAUDE.md").write_text(claude_adapter, encoding="utf-8")

    # 2. Cursor Adapter (.cursorrules / cursor_rules.md)
    cursor_adapter = (
        f"# Cursor Custom Rules Adapter\n"
        f"Generated from Relay Protocol config.\n\n"
        f"{skill_text}\n\n"
        f"## Cursor Specific instructions:\n"
        f"- Display warning alerts if attempting to modify files with open blockers.\n"
        f"- Render high-priority active tasks visually in the cursor sidebar if possible.\n"
    )
    (adapters_dir / "cursor" / "cursor_rules.md").write_text(cursor_adapter, encoding="utf-8")

    # 3. Copilot Adapter (copilot-instructions.md)
    copilot_adapter = (
        f"# GitHub Copilot Rules Adapter\n"
        f"Generated from Relay Protocol config.\n\n"
        f"{skill_text}\n\n"
        f"## Copilot Specific instructions:\n"
        f"- Inline suggestions should respect accepted architectural guardrails (`dec_` events).\n"
    )
    (adapters_dir / "copilot" / "copilot-instructions.md").write_text(copilot_adapter, encoding="utf-8")

    # 4. OpenCode Adapter (opencode_instructions.md)
    opencode_adapter = (
        f"# OpenCode Instructions Adapter\n"
        f"Generated from Relay Protocol config.\n\n"
        f"{skill_text}\n\n"
        f"## OpenCode Specific instructions:\n"
        f"- Parse YAML rules directly when running execution loops.\n"
    )
    (adapters_dir / "opencode" / "opencode_instructions.md").write_text(opencode_adapter, encoding="utf-8")

    print(f"[SUCCESS] Generated 4 agent adapters in: {adapters_dir.relative_to(project_root)}")


if __name__ == "__main__":
    main()
