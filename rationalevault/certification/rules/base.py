from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Protocol, Union

from ..context import CertificationContext
from ..models import ArtifactType, Diagnostic, Finding, RuleResult

class CertificationCheck(ABC):
    """A single atomic check."""
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique ID for the check."""
        pass
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name."""
        pass
        
    @abstractmethod
    def check(self, context: CertificationContext) -> List[Union[Finding, Diagnostic]]:
        """Executes the check and returns findings/diagnostics."""
        pass

@dataclass
class CertificationRule:
    """Groups multiple checks into a logical rule."""
    id: str
    name: str
    category: str
    checks: List[CertificationCheck] = field(default_factory=list)

@dataclass
class RulePack:
    """A collection of rules that apply to specific artifact types."""
    id: str
    artifact_types: List[ArtifactType]
    rules: List[CertificationRule] = field(default_factory=list)
