from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional
from rationalevault.memory.models import MemoryRecord
from rationalevault.knowledge.models import EpistemicStatus


@dataclass(frozen=True)
class ContradictionFinding:
    finding_id: str
    rule_a_id: str
    rule_b_id: str
    contradiction_type: str  # opposite_assertion | exclusive_config | duplicate_conflicting
    severity: str  # warning | critical
    evidence: str
    suggested_status: EpistemicStatus
    suppressed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_a_id": self.rule_a_id,
            "rule_b_id": self.rule_b_id,
            "contradiction_type": self.contradiction_type,
            "severity": self.severity,
            "evidence": self.evidence,
            "suggested_status": self.suggested_status.value,
            "suppressed": self.suppressed,
        }

    @staticmethod
    def generate_finding_id(contradiction_type: str, rule_a_id: str, rule_b_id: str, detail_key: str = "") -> str:
        pair = ":".join(sorted([rule_a_id, rule_b_id]))
        data = f"{contradiction_type}:{pair}:{detail_key}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"CONTR-{h}"


class ContradictionEngine:
    """Algorithmically identifies and flags conflicting project rules or memory records."""

    @staticmethod
    def detect(records: list[MemoryRecord], suppressed_ids: Optional[set[str]] = None) -> list[ContradictionFinding]:
        findings: list[ContradictionFinding] = []
        suppressed_set = suppressed_ids or set()

        # 1. Detect duplicate IDs with conflicting payloads
        id_map: dict[str, MemoryRecord] = {}
        for r in records:
            if r.id in id_map:
                existing = id_map[r.id]
                if existing.title != r.title or existing.content != r.content:
                    fid = ContradictionFinding.generate_finding_id("duplicate_conflicting", existing.id, r.id)
                    findings.append(ContradictionFinding(
                        finding_id=fid,
                        rule_a_id=existing.id,
                        rule_b_id=r.id,
                        contradiction_type="duplicate_conflicting",
                        severity="critical",
                        evidence=f"Duplicate ID '{r.id}' has conflicting content. A: '{existing.title}', B: '{r.title}'",
                        suggested_status=EpistemicStatus.CONFLICTED,
                        suppressed=fid in suppressed_set
                    ))
            else:
                id_map[r.id] = r

        # 2. Detect exact opposite assertions and mutually exclusive configurations
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                r_a = records[i]
                r_b = records[j]

                content_a = r_a.content.lower().strip()
                content_b = r_b.content.lower().strip()

                # Parse simple config values (e.g. key = value or key: value)
                def parse_configs(text: str) -> dict[str, str]:
                    configs = {}
                    for line in text.splitlines():
                        if "=" in line:
                            parts = line.split("=", 1)
                            configs[parts[0].strip()] = parts[1].strip()
                        elif ":" in line:
                            parts = line.split(":", 1)
                            configs[parts[0].strip()] = parts[1].strip()
                    return configs

                cfg_a = parse_configs(content_a)
                cfg_b = parse_configs(content_b)

                for key, val_a in cfg_a.items():
                    if key in cfg_b:
                        val_b = cfg_b[key]
                        if val_a != val_b:
                            fid = ContradictionFinding.generate_finding_id("exclusive_config", r_a.id, r_b.id, key)
                            findings.append(ContradictionFinding(
                                finding_id=fid,
                                rule_a_id=r_a.id,
                                rule_b_id=r_b.id,
                                contradiction_type="exclusive_config",
                                severity="critical",
                                evidence=f"Mutually exclusive configuration for '{key}': '{val_a}' vs '{val_b}'",
                                suggested_status=EpistemicStatus.CONFLICTED,
                                suppressed=fid in suppressed_set
                            ))

                # Check opposite assertions (enable/disable, allow/forbid, use/avoid, etc.)
                keywords = ["postgres", "sqlite", "mysql", "pooling", "migration"]
                for kw in keywords:
                    if kw in content_a and kw in content_b:
                        polarities = [
                            ("enable", "disable"),
                            ("allow", "forbid"),
                            ("allow", "prohibit"),
                            ("always", "never"),
                            ("use", "avoid"),
                            ("shall", "shall not")
                        ]
                        for pol_a, pol_b in polarities:
                            if (pol_a in content_a and pol_b in content_b) or (pol_b in content_a and pol_a in content_b):
                                fid = ContradictionFinding.generate_finding_id("opposite_assertion", r_a.id, r_b.id, kw)
                                findings.append(ContradictionFinding(
                                    finding_id=fid,
                                    rule_a_id=r_a.id,
                                    rule_b_id=r_b.id,
                                    contradiction_type="opposite_assertion",
                                    severity="warning",
                                    evidence=f"Opposite assertions found regarding '{kw}': '{pol_a}' vs '{pol_b}'",
                                    suggested_status=EpistemicStatus.CONFLICTED,
                                    suppressed=fid in suppressed_set
                                ))

        return findings
