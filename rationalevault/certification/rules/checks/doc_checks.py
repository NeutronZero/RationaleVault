from typing import List, Union
import ast

from ...context import CertificationContext
from ...models import Diagnostic, Finding, Severity, SourceLocation
from ..base import CertificationCheck

class CheckReadmeExists(CertificationCheck):
    @property
    def id(self) -> str:
        return "RV020"
        
    @property
    def name(self) -> str:
        return "README Check"
        
    def check(self, context: CertificationContext) -> List[Union[Finding, Diagnostic]]:
        readme_path = context.target_path / "README.md"
        if not readme_path.exists():
            return [Finding(
                id=self.id,
                severity=Severity.ERROR,
                message="Missing README.md in extension root.",
                remediation="Create a README.md documenting the extension's purpose and usage."
            )]
        return []

class CheckPublicDocstrings(CertificationCheck):
    @property
    def id(self) -> str:
        return "RV021"
        
    @property
    def name(self) -> str:
        return "Public Docstrings Check"
        
    def check(self, context: CertificationContext) -> List[Union[Finding, Diagnostic]]:
        findings = []
        for file_path, tree in context.ast_trees.items():
            if "__init__" in file_path:
                continue
                
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    if not node.name.startswith("_"):
                        if not ast.get_docstring(node):
                            findings.append(Finding(
                                id=self.id,
                                severity=Severity.WARNING,
                                message=f"Public entity '{node.name}' lacks a docstring.",
                                remediation="Add a docstring explaining the purpose and usage.",
                                location=SourceLocation(file=file_path, line=node.lineno)
                            ))
        return findings
