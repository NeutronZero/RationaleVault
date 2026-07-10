import ast
from typing import List, Union

from ...context import CertificationContext
from ...models import Diagnostic, Finding, Severity, SourceLocation
from ..base import CertificationCheck

class CheckNoInternalImports(CertificationCheck):
    @property
    def id(self) -> str:
        return "RV010"
        
    @property
    def name(self) -> str:
        return "Internal Imports Check"
        
    def check(self, context: CertificationContext) -> List[Union[Finding, Diagnostic]]:
        findings = []
        for file_path, tree in context.ast_trees.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("rationalevault.internal."):
                            findings.append(self._make_finding(file_path, node, alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("rationalevault.internal"):
                        findings.append(self._make_finding(file_path, node, node.module))
        return findings
        
    def _make_finding(self, file_path: str, node: ast.AST, module: str) -> Finding:
        return Finding(
            id=self.id,
            severity=Severity.ERROR,
            message=f"Forbidden import from internal module '{module}'.",
            remediation="Use public APIs exported from rationalevault instead.",
            location=SourceLocation(file=file_path, line=getattr(node, 'lineno', 0))
        )

class CheckReducerPurity(CertificationCheck):
    @property
    def id(self) -> str:
        return "RV011"
        
    @property
    def name(self) -> str:
        return "Reducer Purity Check"
        
    def check(self, context: CertificationContext) -> List[Union[Finding, Diagnostic]]:
        findings = []
        forbidden_calls = {
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "uuid.uuid4",
            "random.random",
            "random.randint",
            "random.choice",
            "open",
            "requests.get",
            "requests.post",
        }
        
        for file_path, tree in context.ast_trees.items():
            # In a real AST guard, we'd specifically look inside @reducer decorated functions.
            # For simplicity, we flag these calls anywhere in the file if it's a projection.
            # We can refine this to look for classes inheriting from Projection.
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    call_name = self._get_call_name(node.func)
                    if call_name in forbidden_calls:
                        findings.append(Finding(
                            id=self.id,
                            severity=Severity.ERROR,
                            message=f"Impure function call '{call_name}' detected.",
                            remediation="Reducers must be pure. Move impure logic to side-effects or command handlers.",
                            location=SourceLocation(file=file_path, line=getattr(node, 'lineno', 0))
                        ))
                        
        return findings
        
    def _get_call_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            base = self._get_call_name(node.value)
            if base:
                return f"{base}.{node.attr}"
            return node.attr
        return ""
