from ..context import CertificationContext
from ..engine import CertificationStage

class ReportingStage(CertificationStage):
    @property
    def id(self) -> str:
        return "reporting"
        
    def execute(self, context: CertificationContext) -> CertificationContext:
        # Final aggregation logic if needed, but Engine handles the actual report building.
        # This could sort findings by severity, etc.
        context.findings.sort(key=lambda f: (f.severity.value, f.id))
        return context
