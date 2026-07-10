from dataclasses import dataclass, field
from typing import Optional

from .diagnostic import Diagnostic, Severity

@dataclass
class SourceLocation:
    file: str
    line: Optional[int] = None
    column: Optional[int] = None

@dataclass
class Finding:
    id: str  # e.g., "RV001"
    severity: Severity
    message: str
    remediation: str
    location: Optional[SourceLocation] = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
