from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import ClassVar, Mapping

from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.schema.events import EventRecord

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class AliasMetadata:
    canonical: str
    source_event_seq: int
    source_event_type: str

@dataclass(frozen=True)
class AliasMap:
    aliases: Mapping[str, str]
    metadata: Mapping[str, AliasMetadata] = field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        return dict(self.aliases)


class AliasProjection(BaseProjection):
    """AliasProjection extracts project-specific acronyms and lexicons from the event stream.
    
    Supports:
    - PROJECT_CREATED config aliases / acronyms
    - ALIAS_ADDED or GLOSSARY_ENTRY_CREATED events
    """
    projection_name: ClassVar[str] = "Alias"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
    dependencies: ClassVar[list[type[BaseProjection]]] = []
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 5

    @staticmethod
    def project(events: list[EventRecord]) -> AliasMap:
        aliases_dict: dict[str, str] = {}
        metadata_dict: dict[str, AliasMetadata] = {}

        # Sort events by sequence to enforce deterministic latest-wins ordering
        sorted_events = sorted(events, key=lambda e: e.event_sequence)

        for event in sorted_events:
            et_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
            p = event.payload or {}

            # 1. PROJECT_CREATED Config
            if et_str == "PROJECT_CREATED":
                config = p.get("config") or {}
                config_aliases = config.get("aliases") or config.get("acronyms") or {}
                for k, v in config_aliases.items():
                    key = k.strip().lower()
                    val = str(v).strip()
                    if key in aliases_dict:
                        old_meta = metadata_dict[key]
                        logger.warning(
                            "Conflicting alias override for '%s': '%s' (seq %d) replaced by '%s' (seq %d)",
                            key, old_meta.canonical, old_meta.source_event_seq, val, event.event_sequence
                        )
                    aliases_dict[key] = val
                    metadata_dict[key] = AliasMetadata(
                        canonical=val,
                        source_event_seq=event.event_sequence,
                        source_event_type=et_str
                    )

            # 2. ALIAS_ADDED or GLOSSARY_ENTRY_CREATED
            elif et_str in ("ALIAS_ADDED", "GLOSSARY_ENTRY_CREATED"):
                alias_key = p.get("alias") or p.get("term")
                canonical_val = p.get("canonical") or p.get("definition")
                if alias_key is not None and canonical_val is not None:
                    key = str(alias_key).strip().lower()
                    val = str(canonical_val).strip()
                    if key in aliases_dict:
                        old_meta = metadata_dict[key]
                        logger.warning(
                            "Conflicting alias override for '%s': '%s' (seq %d) replaced by '%s' (seq %d)",
                            key, old_meta.canonical, old_meta.source_event_seq, val, event.event_sequence
                        )
                    aliases_dict[key] = val
                    metadata_dict[key] = AliasMetadata(
                        canonical=val,
                        source_event_seq=event.event_sequence,
                        source_event_type=et_str
                    )

        return AliasMap(aliases=aliases_dict, metadata=metadata_dict)
