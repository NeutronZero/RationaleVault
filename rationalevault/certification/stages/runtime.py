import subprocess
import sys

from ..context import CertificationContext
from ..engine import CertificationStage
from ..models import ArtifactType, Diagnostic, Finding, Severity, RuleResult

class RuntimeStage(CertificationStage):
    @property
    def id(self) -> str:
        return "runtime"
        
    def execute(self, context: CertificationContext) -> CertificationContext:
        if not context.artifact_type:
            return context
            
        # Example for Projection: Run pytest over its tests to see if conformance passes
        # This is a simplified runtime check. In reality, we'd invoke the specific suite.
        # Here we just run pytest if a tests/ directory exists.
        
        tests_dir = context.target_path / "tests"
        if tests_dir.exists():
            try:
                # Run isolated pytest
                res = subprocess.run(
                    [sys.executable, "-m", "pytest", str(tests_dir), "-q"],
                    capture_output=True,
                    text=True,
                    cwd=str(context.target_path)
                )
                
                if res.returncode != 0:
                    context.findings.append(Finding(
                        id="RV004",
                        severity=Severity.ERROR,
                        message="Runtime test suite failed.",
                        remediation="Ensure all tests and conformance suites pass locally.",
                        diagnostics=[Diagnostic(id="test_output", name="Test Output", value=res.stdout[-1000:])]
                    ))
                    
                # Store RuleResult for Conformance
                context.rule_results["Conformance"] = RuleResult(
                    rule="Runtime Conformance",
                    passed=(res.returncode == 0),
                    checks=1,
                    failures=1 if res.returncode != 0 else 0
                )
                
            except Exception as e:
                context.findings.append(Finding(
                    id="RV004",
                    severity=Severity.ERROR,
                    message=f"Failed to execute runtime suite: {e}",
                    remediation="Check test configuration."
                ))
                
        return context
