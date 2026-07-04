"""
RationaleVault Memory Policy Engine — Contracts for configurable memory behavior.

The Policy Engine sits behind the MemoryBroker, controlling:
  - Retrieval strategy and scoring
  - Cache behavior and invalidation
  - Provenance requirements
  - Write validation and importance thresholds
  - Deduplication strategy

Design rules:
  - Policies are immutable after construction.
  - Default policies are conservative (safe for all use cases).
  - Policies compose: MemoryPolicy = Retrieval + Cache + Provenance + Write + Dedup.
  - Policy changes don't affect agent code — only broker behavior.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class RetrievalStrategy(str, Enum):
    """How memories are retrieved."""
    LEXICAL = "LEXICAL"            # BM25 only
    SEMANTIC = "SEMANTIC"          # Vector search only
    HYBRID = "HYBRID"              # BM25 + Vector with RRF
    GRAPH = "GRAPH"                # Knowledge graph traversal
    ADAPTIVE = "ADAPTIVE"          # Strategy selected by query intent


class CacheInvalidation(str, Enum):
    """When cached contexts are invalidated."""
    TTL = "TTL"                    # Time-to-live
    LRU = "LRU"                    # Least recently used
    EVENT_DRIVEN = "EVENT_DRIVEN"  # Invalidate on new events
    MANUAL = "MANUAL"              # Agent-controlled


class DedupStrategy(str, Enum):
    """How duplicate memories are handled."""
    EXACT = "EXACT"                # Deterministic ID match
    SIMILARITY = "SIMILARITY"      # Jaccard similarity threshold
    SEMANTIC = "SEMANTIC"          # Embedding similarity
    NONE = "NONE"                  # No deduplication


class ProvenanceDepth(str, Enum):
    """How deep provenance chains are traced."""
    NONE = "NONE"                  # No provenance
    SHALLOW = "SHALLOW"            # Source events only
    FULL = "FULL"                  # Events + memories + knowledge
    COMPLETE = "COMPLETE"          # Full graph traversal


class WriteValidation(str, Enum):
    """How write requests are validated."""
    NONE = "NONE"                  # No validation
    SCHEMA = "SCHEMA"              # Schema validation only
    IMPORTANCE = "IMPORTANCE"       # Importance threshold check
    FULL = "FULL"                  # Schema + importance + dedup check


# =====================================================================
# Retrieval Policy
# =====================================================================

@dataclass(frozen=True)
class RetrievalPolicy:
    """
    Controls how memories are retrieved and scored.

    MPOL-RET-[hash] — immutable policy identifier.
    """
    policy_id: str                  # MPOL-RET-[hash]
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    max_results: int = 10
    min_score: float = 0.0
    boost_critical: float = 1.5    # Multiplier for critical importance
    boost_recent_days: int = 7     # Days window for recency boost
    recency_decay_half_life_days: int = 30
    lifecycle_penalty_superseded: float = -5.0
    lifecycle_penalty_archived: float = -10.0
    type_weights: dict[str, float] = field(default_factory=lambda: {
        "DECISION": 2.0,
        "DECISION_RATIONALE": 1.5,
        "LESSON_LEARNED": 1.2,
        "FAILURE": 1.8,
        "ARCHITECTURE": 1.0,
        "IMPLEMENTATION_NOTE": 0.8,
        "RESEARCH": 1.0,
        "WORKFLOW": 1.0,
    })

    @staticmethod
    def generate_policy_id(name: str = "default") -> str:
        data = f"retrieval_policy:{name}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MPOL-RET-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "strategy": self.strategy.value,
            "max_results": self.max_results,
            "min_score": self.min_score,
            "boost_critical": self.boost_critical,
            "boost_recent_days": self.boost_recent_days,
            "recency_decay_half_life_days": self.recency_decay_half_life_days,
            "lifecycle_penalty_superseded": self.lifecycle_penalty_superseded,
            "lifecycle_penalty_archived": self.lifecycle_penalty_archived,
            "type_weights": self.type_weights,
        }


# =====================================================================
# Cache Policy
# =====================================================================

@dataclass(frozen=True)
class CachePolicy:
    """
    Controls caching behavior for memory contexts.

    MPOL-CAC-[hash] — immutable policy identifier.
    """
    policy_id: str                  # MPOL-CAC-[hash]
    enabled: bool = True
    invalidation: CacheInvalidation = CacheInvalidation.TTL
    ttl_seconds: int = 300         # 5 minutes
    max_entries: int = 100
    max_age_seconds: int = 3600    # 1 hour hard limit

    @staticmethod
    def generate_policy_id(name: str = "default") -> str:
        data = f"cache_policy:{name}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MPOL-CAC-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "enabled": self.enabled,
            "invalidation": self.invalidation.value,
            "ttl_seconds": self.ttl_seconds,
            "max_entries": self.max_entries,
            "max_age_seconds": self.max_age_seconds,
        }


# =====================================================================
# Provenance Policy
# =====================================================================

@dataclass(frozen=True)
class ProvenancePolicy:
    """
    Controls provenance requirements for memory results.

    MPOL-PRV-[hash] — immutable policy identifier.
    """
    policy_id: str                  # MPOL-PRV-[hash]
    depth: ProvenanceDepth = ProvenanceDepth.FULL
    require_source_events: bool = True
    require_source_memories: bool = False
    min_chain_length: int = 0
    max_chain_length: int = 10
    include_retrieval_path: bool = True

    @staticmethod
    def generate_policy_id(name: str = "default") -> str:
        data = f"provenance_policy:{name}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MPOL-PRV-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "depth": self.depth.value,
            "require_source_events": self.require_source_events,
            "require_source_memories": self.require_source_memories,
            "min_chain_length": self.min_chain_length,
            "max_chain_length": self.max_chain_length,
            "include_retrieval_path": self.include_retrieval_path,
        }


# =====================================================================
# Write Policy
# =====================================================================

@dataclass(frozen=True)
class WritePolicy:
    """
    Controls write behavior for memory records.

    MPOL-WRT-[hash] — immutable policy identifier.
    """
    policy_id: str                  # MPOL-WRT-[hash]
    validation: WriteValidation = WriteValidation.FULL
    min_importance: str = "low"     # Minimum importance to accept
    max_content_length: int = 10000
    require_project_id: bool = False
    require_tags: bool = False
    allowed_memory_types: frozenset[str] | None = None  # None = all allowed

    @staticmethod
    def generate_policy_id(name: str = "default") -> str:
        data = f"write_policy:{name}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MPOL-WRT-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "validation": self.validation.value,
            "min_importance": self.min_importance,
            "max_content_length": self.max_content_length,
            "require_project_id": self.require_project_id,
            "require_tags": self.require_tags,
            "allowed_memory_types": sorted(self.allowed_memory_types) if self.allowed_memory_types else None,
        }


# =====================================================================
# Dedup Policy
# =====================================================================

@dataclass(frozen=True)
class DedupPolicy:
    """
    Controls deduplication behavior for memory writes.

    MPOL-DUP-[hash] — immutable policy identifier.
    """
    policy_id: str                  # MPOL-DUP-[hash]
    strategy: DedupStrategy = DedupStrategy.EXACT
    similarity_threshold: float = 0.35  # Jaccard threshold for SIMILARITY
    merge_on_dedup: bool = False    # Merge metadata on duplicate
    log_dedup_events: bool = True   # Record dedup events

    @staticmethod
    def generate_policy_id(name: str = "default") -> str:
        data = f"dedup_policy:{name}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MPOL-DUP-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "strategy": self.strategy.value,
            "similarity_threshold": self.similarity_threshold,
            "merge_on_dedup": self.merge_on_dedup,
            "log_dedup_events": self.log_dedup_events,
        }


# =====================================================================
# Composite Memory Policy
# =====================================================================

@dataclass(frozen=True)
class MemoryPolicy:
    """
    Composite policy combining all five policy dimensions.

    MPOL-[hash] — the top-level policy identifier.
    """
    policy_id: str                  # MPOL-[hash]
    name: str
    description: str = ""
    retrieval: RetrievalPolicy = field(default_factory=lambda: RetrievalPolicy(
        policy_id=RetrievalPolicy.generate_policy_id("default"),
    ))
    cache: CachePolicy = field(default_factory=lambda: CachePolicy(
        policy_id=CachePolicy.generate_policy_id("default"),
    ))
    provenance: ProvenancePolicy = field(default_factory=lambda: ProvenancePolicy(
        policy_id=ProvenancePolicy.generate_policy_id("default"),
    ))
    write: WritePolicy = field(default_factory=lambda: WritePolicy(
        policy_id=WritePolicy.generate_policy_id("default"),
    ))
    dedup: DedupPolicy = field(default_factory=lambda: DedupPolicy(
        policy_id=DedupPolicy.generate_policy_id("default"),
    ))

    @staticmethod
    def generate_policy_id(name: str) -> str:
        data = f"memory_policy:{name}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"MPOL-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "retrieval": self.retrieval.to_dict(),
            "cache": self.cache.to_dict(),
            "provenance": self.provenance.to_dict(),
            "write": self.write.to_dict(),
            "dedup": self.dedup.to_dict(),
        }

    @staticmethod
    def default() -> MemoryPolicy:
        """Return the default conservative policy."""
        return MemoryPolicy(
            policy_id=MemoryPolicy.generate_policy_id("default"),
            name="default",
            description="Default conservative policy for all memory operations",
        )

    @staticmethod
    def aggressive() -> MemoryPolicy:
        """Return an aggressive policy for high-throughput scenarios."""
        return MemoryPolicy(
            policy_id=MemoryPolicy.generate_policy_id("aggressive"),
            name="aggressive",
            description="Aggressive policy with relaxed dedup and caching",
            retrieval=RetrievalPolicy(
                policy_id=RetrievalPolicy.generate_policy_id("aggressive"),
                max_results=20,
                boost_critical=2.0,
            ),
            cache=CachePolicy(
                policy_id=CachePolicy.generate_policy_id("aggressive"),
                ttl_seconds=600,
                max_entries=500,
            ),
            dedup=DedupPolicy(
                policy_id=DedupPolicy.generate_policy_id("aggressive"),
                strategy=DedupStrategy.SIMILARITY,
                similarity_threshold=0.5,
            ),
        )

    @staticmethod
    def strict() -> MemoryPolicy:
        """Return a strict policy for audit-critical scenarios."""
        return MemoryPolicy(
            policy_id=MemoryPolicy.generate_policy_id("strict"),
            name="strict",
            description="Strict policy with full provenance and validation",
            provenance=ProvenancePolicy(
                policy_id=ProvenancePolicy.generate_policy_id("strict"),
                depth=ProvenanceDepth.COMPLETE,
                require_source_events=True,
                require_source_memories=True,
                min_chain_length=1,
            ),
            write=WritePolicy(
                policy_id=WritePolicy.generate_policy_id("strict"),
                validation=WriteValidation.FULL,
                require_project_id=True,
                require_tags=True,
            ),
            dedup=DedupPolicy(
                policy_id=DedupPolicy.generate_policy_id("strict"),
                strategy=DedupStrategy.SIMILARITY,
                similarity_threshold=0.25,
                merge_on_dedup=True,
            ),
        )
