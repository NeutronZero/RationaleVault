import time
from typing import Protocol, Type, Dict, List

from .context import CertificationContext
from .models import CertificationReport

class CertificationStage(Protocol):
    @property
    def id(self) -> str:
        ...
        
    def execute(self, context: CertificationContext) -> CertificationContext:
        ...

class CertificationEngine:
    def __init__(self, stages: List[CertificationStage]):
        self.stages = stages

    def run(self, context: CertificationContext) -> CertificationReport:
        stage_timings: Dict[str, float] = {}
        
        for stage in self.stages:
            start = time.perf_counter()
            
            try:
                context = stage.execute(context)
            except Exception as e:
                import traceback
                # Add a critical finding if a stage crashes
                from .models import Finding, Severity, Diagnostic
                context.findings.append(Finding(
                    id="RV999",
                    severity=Severity.ERROR,
                    message=f"Stage {stage.id} crashed: {str(e)}",
                    remediation="Fix the underlying exception.",
                    diagnostics=[Diagnostic(id="stacktrace", name="Stack Trace", value=traceback.format_exc())]
                ))
                break # Stop pipeline on crash
                
            elapsed = time.perf_counter() - start
            stage_timings[stage.id] = elapsed * 1000 # Convert to ms
            
        context.metadata["stage_timings"] = stage_timings
        
        return self._build_report(context)

    def _build_report(self, context: CertificationContext) -> CertificationReport:
        import platform
        import sys
        from rationalevault import __version__ as framework_version
        from datetime import datetime
        from .models import CertificationReport, ReportMetadata, ArtifactType
        
        reproducibility = ReportMetadata(
            python_version=sys.version.split(" ")[0],
            platform=platform.platform(),
            certification_profile="rationalevault-default",
            elapsed_ms=sum(context.metadata.get("stage_timings", {}).values())
        )
        
        return CertificationReport(
            schema_version="1.0",
            engine_version="1.0",
            framework_version=framework_version,
            rule_catalog_version="v1",
            timestamp=datetime.utcnow(),
            artifact_type=context.artifact_type or ArtifactType.PROJECTION,
            reproducibility=reproducibility,
            findings=context.findings,
            diagnostics=context.diagnostics,
            rule_results=context.rule_results
        )
