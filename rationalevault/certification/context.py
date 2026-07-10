from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import ast

from .models import (
    ArtifactType,
    Diagnostic,
    ExtensionManifest,
    Finding,
    RuleResult,
)

@dataclass
class CertificationContext:
    target_path: Path
    artifact_type: Optional[ArtifactType] = None
    manifest: Optional[ExtensionManifest] = None
    ast_trees: dict[str, ast.AST] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    rule_results: dict[str, RuleResult] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
