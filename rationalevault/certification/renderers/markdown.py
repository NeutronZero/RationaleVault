from .base import ReportRenderer
from .json import JsonRenderer
from .terminal import TerminalRenderer

class MarkdownRenderer(ReportRenderer):
    def render(self, report) -> str:
        lines = []
        lines.append("# RationaleVault Certification Report")
        status_badge = "✅ CERTIFIED" if report.passed else "❌ FAILED"
        lines.append(f"**Status**: {status_badge}")
        lines.append(f"**Artifact Type**: `{report.artifact_type.name}`")
        lines.append(f"**Timestamp**: `{report.timestamp.isoformat()}`")
        
        lines.append("## Rule Results")
        lines.append("| Rule | Status | Failures |")
        lines.append("|---|---|---|")
        for rule_id, res in report.rule_results.items():
            st = "✅" if res.passed else "❌"
            lines.append(f"| {res.rule} | {st} | {res.failures}/{res.checks} |")
            
        if report.findings:
            lines.append("## Findings")
            for f in report.findings:
                lines.append(f"### [{f.severity.name}] {f.id}")
                lines.append(f"**Message**: {f.message}")
                lines.append(f"**Remediation**: {f.remediation}")
                if f.location:
                    lines.append(f"**Location**: `{f.location.file}:{f.location.line}`")
                lines.append("")
                
        return "\n".join(lines)
