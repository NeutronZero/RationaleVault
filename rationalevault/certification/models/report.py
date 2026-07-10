from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .artifact import ArtifactType
from .diagnostic import Diagnostic
from .finding import Finding
from .rule_result import RuleResult

@dataclass
class ReportMetadata:
    python_version: str
    platform: str
    certification_profile: str
    elapsed_ms: float

@dataclass
class CertificationReport:
    schema_version: str
    engine_version: str
    framework_version: str
    rule_catalog_version: str
    timestamp: datetime
    artifact_type: ArtifactType
    reproducibility: ReportMetadata
    findings: list[Finding] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    rule_results: dict[str, RuleResult] = field(default_factory=dict)
    
    @property
    def passed(self) -> bool:
        from .diagnostic import Severity
        return not any(f.severity == Severity.ERROR for f in self.findings)
