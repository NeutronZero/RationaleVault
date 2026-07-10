from dataclasses import dataclass

@dataclass
class RuleResult:
    rule: str
    passed: bool
    checks: int
    failures: int
