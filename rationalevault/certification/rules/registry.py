from typing import List

from ..models import ArtifactType
from .base import RulePack

class RulePackRegistry:
    def __init__(self):
        self._packs: List[RulePack] = []

    def register(self, pack: RulePack) -> None:
        self._packs.append(pack)

    def get_packs_for_artifact(self, artifact_type: ArtifactType) -> List[RulePack]:
        return [p for p in self._packs if artifact_type in p.artifact_types]

# Global registry
rule_pack_registry = RulePackRegistry()
