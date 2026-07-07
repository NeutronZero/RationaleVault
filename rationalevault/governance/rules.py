"""Governance rules module defining registration and registry functions."""

from __future__ import annotations

from rationalevault.governance.state import GovernanceRule


class GovernanceRuleRegistry:
    """Manages explicit registration and sorting of governance rules."""

    def __init__(self) -> None:
        self._rules: dict[tuple[str, int], GovernanceRule] = {}
        self._frozen = False

    def register(self, rule: GovernanceRule) -> None:
        """Register a governance rule. Raises if frozen or duplicate."""
        if self._frozen:
            raise RuntimeError("Registry is frozen")
        key = (rule.metadata.id, rule.metadata.version)
        if key in self._rules:
            raise ValueError(f"Rule {key} already registered")
        self._rules[key] = rule

    def freeze(self) -> None:
        """Freeze the registry to prevent modifications."""
        self._frozen = True

    def rules(self) -> list[GovernanceRule]:
        """Return rules in deterministic order. Must be frozen."""
        if not self._frozen:
            raise RuntimeError("Registry must be frozen before use")
        return [self._rules[k] for k in sorted(self._rules.keys())]

    @property
    def rule_ids(self) -> list[str]:
        return [r.metadata.id for r in self.rules()]
