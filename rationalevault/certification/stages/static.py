import ast
from pathlib import Path

from ..context import CertificationContext
from ..engine import CertificationStage
from ..models import ArtifactType, RuleResult
from ..rules import rule_pack_registry

class StaticAnalysisStage(CertificationStage):
    @property
    def id(self) -> str:
        return "static"
        
    def execute(self, context: CertificationContext) -> CertificationContext:
        if not context.artifact_type:
            return context
            
        # 1. Parse all ASTs
        for py_file in context.target_path.rglob("*.py"):
            if "venv" in py_file.parts or ".tox" in py_file.parts:
                continue
                
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(py_file))
                context.ast_trees[str(py_file)] = tree
            except SyntaxError:
                pass # Optionally report syntax errors
                
        # 2. Get applicable RulePacks
        packs = rule_pack_registry.get_packs_for_artifact(context.artifact_type)
        
        # 3. Execute all rules and checks
        for pack in packs:
            for rule in pack.rules:
                passed = True
                total_checks = len(rule.checks)
                failures = 0
                
                for check in rule.checks:
                    results = check.check(context)
                    for res in results:
                        from ..models import Finding, Diagnostic
                        if isinstance(res, Finding):
                            context.findings.append(res)
                            from ..models import Severity
                            if res.severity == Severity.ERROR:
                                failures += 1
                                passed = False
                        elif isinstance(res, Diagnostic):
                            context.diagnostics.append(res)
                            
                context.rule_results[rule.id] = RuleResult(
                    rule=rule.name,
                    passed=passed,
                    checks=total_checks,
                    failures=failures
                )
                
        return context
