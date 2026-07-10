from ..context import CertificationContext
from ..engine import CertificationStage
from ..models import Finding, Severity
from ..compatibility import CompatibilityAnalyzer

class CompatibilityStage(CertificationStage):
    @property
    def id(self) -> str:
        return "compatibility"
        
    def execute(self, context: CertificationContext) -> CertificationContext:
        if not context.manifest:
            return context
            
        supported = context.manifest.supported_rationalevault
        if supported:
            # Check spec
            if not CompatibilityAnalyzer.is_compatible(supported):
                from rationalevault import __version__
                context.findings.append(Finding(
                    id="RV003",
                    severity=Severity.ERROR,
                    message=f"Incompatible framework version. Plugin requires '{supported}', but running '{__version__}'.",
                    remediation="Update the plugin's supported_rationalevault specifier or use a compatible RationaleVault version."
                ))
                
        return context
