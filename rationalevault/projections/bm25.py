from __future__ import annotations
import math
from dataclasses import dataclass
from typing import ClassVar, Mapping, Optional

from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer
from rationalevault.projections.alias import AliasProjection, AliasMap
from rationalevault.schema.events import EventRecord
from rationalevault.memory.models import MemoryRecord
from rationalevault.memory.extractor import extract_memories_from_event


@dataclass(frozen=True)
class BM25Config:
    k1: float = 1.5
    b: float = 0.75


@dataclass(frozen=True)
class BM25IndexState:
    df: Mapping[str, int]
    dl: Mapping[str, int]
    avgdl: float
    tf: Mapping[str, Mapping[str, int]]  # doc_id -> term -> count
    vocabulary_size: int
    document_ids: list[str]
    normalizer_version: str = "1.0.0"

    def score(self, doc_id: str, query_tokens: list[str], config: BM25Config = BM25Config()) -> float:
        """Computes the BM25 score of query_tokens for doc_id."""
        if doc_id not in self.tf:
            return 0.0

        doc_tf = self.tf[doc_id]
        doc_len = self.dl.get(doc_id, 0)
        total_docs = len(self.document_ids)

        if total_docs == 0:
            return 0.0

        score_val = 0.0
        for term in query_tokens:
            term_freq = doc_tf.get(term, 0)
            if term_freq == 0:
                continue

            # Inverse Document Frequency (IDF) with negative handling
            term_df = self.df.get(term, 0)
            idf = math.log((total_docs - term_df + 0.5) / (term_df + 0.5) + 1.0)
            if idf < 0.0:
                idf = 0.0

            # Term frequency normalization
            numerator = term_freq * (config.k1 + 1.0)
            denominator = term_freq + config.k1 * (1.0 - config.b + config.b * (doc_len / (self.avgdl or 1.0)))

            score_val += idf * (numerator / denominator)

        return score_val


class BM25IndexProjection(BaseProjection):
    """BM25IndexProjection builds a lexical search index over active memories extracted from events."""
    projection_name: ClassVar[str] = "BM25"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
    dependencies: ClassVar[list[type[BaseProjection]]] = [AliasProjection]
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 12

    @staticmethod
    def project(events: list[EventRecord], alias_map: Optional[AliasMap] = None) -> BM25IndexState:
        aliases = dict(alias_map.aliases) if alias_map else {}

        # Reconstruct active memory records from event stream
        memories: dict[str, MemoryRecord] = {}
        sorted_events = sorted(events, key=lambda e: e.event_sequence)

        for event in sorted_events:
            et_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
            p = event.payload or {}

            # Process state transitions
            if et_str == "MEMORY_SUPERSEDED":
                m_id = p.get("memory_id")
                if m_id in memories:
                    memories[m_id].lifecycle_status = "superseded"
            elif et_str == "MEMORY_ARCHIVED":
                m_id = p.get("memory_id")
                if m_id in memories:
                    memories[m_id].lifecycle_status = "archived"
            elif et_str == "DECISION_ACCEPTED":
                supersedes = p.get("supersedes")
                if supersedes:
                    for m_id, m in list(memories.items()):
                        if m_id == supersedes or m.title.lower() == supersedes.lower() or m.content.lower() == supersedes.lower():
                            m.lifecycle_status = "superseded"

            # Extract memories
            extracted = extract_memories_from_event(event)
            for m in extracted:
                memories[m.id] = m

        active_memories = [m for m in memories.values() if m.lifecycle_status == "active"]
        return BM25IndexProjection.build_index(active_memories, aliases)

    @staticmethod
    def build_index(memories: list[MemoryRecord], aliases: dict[str, str]) -> BM25IndexState:
        from rationalevault.memory.semantic_search import LexicalPipeline

        df: dict[str, int] = {}
        dl: dict[str, int] = {}
        tf: dict[str, dict[str, int]] = {}
        document_ids: list[str] = []

        total_len = 0
        vocab = set()

        for m in memories:
            doc_id = m.id
            document_ids.append(doc_id)

            text = f"{m.title} {m.content}"
            tokens = LexicalPipeline.process(text, aliases)

            dl[doc_id] = len(tokens)
            total_len += len(tokens)

            doc_tf: dict[str, int] = {}
            for t in tokens:
                doc_tf[t] = doc_tf.get(t, 0) + 1
                vocab.add(t)

            tf[doc_id] = doc_tf

            for t in doc_tf.keys():
                df[t] = df.get(t, 0) + 1

        avgdl = (total_len / len(memories)) if memories else 0.0

        return BM25IndexState(
            df=df,
            dl=dl,
            avgdl=avgdl,
            tf=tf,
            vocabulary_size=len(vocab),
            document_ids=document_ids
        )
