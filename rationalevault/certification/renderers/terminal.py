from ..models import CertificationReport, Severity
from .base import ReportRenderer

class TerminalRenderer(ReportRenderer):
    def render(self, report: CertificationReport) -> str:
        lines = []
        
        # Header
        lines.append("="*60)
        lines.append(f"RationaleVault Certification Report")
        lines.append(f"Artifact Type: {report.artifact_type.name}")
        lines.append(f"Timestamp: {report.timestamp.isoformat()}")
        lines.append("="*60)
        lines.append("")
        
        # Results by Rule
        lines.append("--- Rule Results ---")
        for rule_id, res in report.rule_results.items():
            status = "PASS" if res.passed else "FAIL"
            lines.append(f"[{status}] {res.rule} ({res.failures}/{res.checks} failures)")
        
        lines.append("")
        
        # Findings
        if report.findings:
            lines.append("--- Findings ---")
            for f in report.findings:
                severity_str = f.severity.name
                loc = f" ({f.location.file}:{f.location.line})" if f.location else ""
                lines.append(f"[{severity_str}] {f.id}: {f.message}{loc}")
                lines.append(f"  Remediation: {f.remediation}")
                lines.append("")
        
        # Summary
        lines.append("="*60)
        status = "CERTIFIED" if report.passed else "FAILED"
        lines.append(f"Overall Status: {status}")
        lines.append(f"Time Elapsed: {report.reproducibility.elapsed_ms:.2f} ms")
        lines.append("="*60)
        
        return "\n".join(lines)
