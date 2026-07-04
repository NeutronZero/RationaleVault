"""
RationaleVault Memory Policy Engine Runtime.

The MemoryPolicyEngine applies policies during broker operations:
  - Validates writes against WritePolicy
  - Checks deduplication against DedupPolicy
  - Enforces provenance requirements against ProvenancePolicy
  - Controls caching against CachePolicy
  - Shapes retrieval against RetrievalPolicy
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from rationalevault.memory.integration_models import (
    MemoryQuery,
    MemoryResult,
    MemoryWriteRequest,
    MemoryWriteResult,
)
from rationalevault.memory.policy_models import (
    CacheInvalidation,
    DedupStrategy,
    MemoryPolicy,
    ProvenanceDepth,
    WriteValidation,
)


# =====================================================================
# Helpers
# =====================================================================

def _generate_validation_id(prefix: str, request_id: str) -> str:
    data = f"validation:{prefix}:{request_id}"
    h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
    return f"MWRS-{h}"


def _generate_memory_id(memory_type: str, title: str, content: str) -> str:
    data = f"{memory_type}:{title}:{content}"
    h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:16].upper()
    return f"MEM-{h}"


# =====================================================================
# Importance Ordering
# =====================================================================

_IMPORTANCE_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


# =====================================================================
# Policy Engine
# =====================================================================

@dataclass
class MemoryPolicyEngine:
    """
    Applies memory policies during broker operations.

    The engine is stateless — all state lives in the policies.
    """
    policy: MemoryPolicy = field(default_factory=MemoryPolicy.default)

    # ── Write Validation ────────────────────────────────────────────────

    def validate_write(self, request: MemoryWriteRequest) -> MemoryWriteResult | None:
        """
        Validate a write request against the WritePolicy.

        Returns None if valid, or a MemoryWriteResult with error if invalid.
        """
        wp = self.policy.write

        if wp.validation == WriteValidation.NONE:
            return None

        # Schema validation
        if wp.validation in (WriteValidation.SCHEMA, WriteValidation.FULL):
            if not request.title or not request.title.strip():
                return MemoryWriteResult(
                    result_id=_generate_validation_id("title", request.request_id),
                    request_id=request.request_id,
                    success=False,
                    error="Title cannot be empty",
                )
            if not request.content or not request.content.strip():
                return MemoryWriteResult(
                    result_id=_generate_validation_id("content", request.request_id),
                    request_id=request.request_id,
                    success=False,
                    error="Content cannot be empty",
                )
            if len(request.content) > wp.max_content_length:
                return MemoryWriteResult(
                    result_id=_generate_validation_id("length", request.request_id),
                    request_id=request.request_id,
                    success=False,
                    error=f"Content exceeds max length of {wp.max_content_length}",
                )

        # Importance threshold
        if wp.validation in (WriteValidation.IMPORTANCE, WriteValidation.FULL):
            req_level = _IMPORTANCE_ORDER.get(request.importance, 0)
            min_level = _IMPORTANCE_ORDER.get(wp.min_importance, 0)
            if req_level < min_level:
                return MemoryWriteResult(
                    result_id=_generate_validation_id("importance", request.request_id),
                    request_id=request.request_id,
                    success=False,
                    error=f"Importance '{request.importance}' below minimum '{wp.min_importance}'",
                )

        # Project ID requirement
        if wp.require_project_id and not request.project_id:
            return MemoryWriteResult(
                result_id=_generate_validation_id("project", request.request_id),
                request_id=request.request_id,
                success=False,
                error="project_id is required",
            )

        # Tags requirement
        if wp.require_tags and not request.tags:
            return MemoryWriteResult(
                result_id=_generate_validation_id("tags", request.request_id),
                request_id=request.request_id,
                success=False,
                error="At least one tag is required",
            )

        # Memory type filter
        if wp.allowed_memory_types and request.memory_type.value not in wp.allowed_memory_types:
            return MemoryWriteResult(
                result_id=MemoryWriteResult.generate_result_id("VALIDATION", request.request_id),
                request_id=request.request_id,
                success=False,
                error=f"Memory type '{request.memory_type.value}' not allowed",
            )

        return None  # Valid

    # ── Deduplication Check ─────────────────────────────────────────────

    def check_dedup(
        self,
        request: MemoryWriteRequest,
        existing_records: list[Any],
    ) -> tuple[bool, str | None]:
        """
        Check if a write would be a duplicate.

        Returns (is_duplicate, duplicate_of_id).
        """
        dp = self.policy.dedup

        if dp.strategy == DedupStrategy.NONE:
            return False, None

        if dp.strategy == DedupStrategy.EXACT:
            # Deterministic ID match
            new_id = _generate_memory_id(request.memory_type.value, request.title, request.content)

            for record in existing_records:
                if str(record.id) == new_id:
                    return True, str(record.id)
            return False, None

        if dp.strategy == DedupStrategy.SIMILARITY:
            # Jaccard similarity on tokens
            new_tokens = set(request.title.lower().split()) | set(request.content.lower().split())
            for record in existing_records:
                existing_tokens = set(record.title.lower().split()) | set(record.content.lower().split())
                if new_tokens and existing_tokens:
                    intersection = new_tokens & existing_tokens
                    union = new_tokens | existing_tokens
                    similarity = len(intersection) / len(union) if union else 0.0
                    if similarity >= dp.similarity_threshold:
                        return True, str(record.id)
            return False, None

        return False, None

    # ── Provenance Enforcement ──────────────────────────────────────────

    def enforce_provenance(self, result: MemoryResult) -> MemoryResult:
        """
        Enforce provenance requirements on a memory result.

        Filters or enriches based on ProvenancePolicy.
        """
        pp = self.policy.provenance

        if pp.depth == ProvenanceDepth.NONE:
            # Strip provenance
            return MemoryResult(
                result_id=result.result_id,
                memory_id=result.memory_id,
                memory_type=result.memory_type,
                title=result.title,
                content=result.content,
                score=result.score,
                lifecycle_state=result.lifecycle_state,
                confidence=result.confidence,
                reference_count=result.reference_count,
                reasons=result.reasons,
            )

        # Validate chain length
        chain_length = len(result.source_event_ids) + len(result.source_memory_ids)
        if chain_length < pp.min_chain_length:
            return MemoryResult(
                result_id=result.result_id,
                memory_id=result.memory_id,
                memory_type=result.memory_type,
                title=result.title,
                content=result.content,
                score=result.score * 0.5,  # Penalize insufficient provenance
                lifecycle_state=result.lifecycle_state,
                confidence=result.confidence * 0.5,
                reference_count=result.reference_count,
                reasons=result.reasons + ["insufficient_provenance"],
                retrieval_path=result.retrieval_path,
                source_event_ids=result.source_event_ids,
                source_memory_ids=result.source_memory_ids,
            )

        return result

    # ── Retrieval Shaping ───────────────────────────────────────────────

    def shape_retrieval(self, results: list[MemoryResult]) -> list[MemoryResult]:
        """
        Shape retrieval results according to RetrievalPolicy.

        Applies type weights, importance boosts, and lifecycle penalties.
        """
        rp = self.policy.retrieval

        shaped = []
        for r in results:
            # Apply type weight
            type_weight = rp.type_weights.get(r.memory_type.value, 1.0)
            adjusted_score = r.score * type_weight

            # Apply importance boost for critical
            if r.reference_count >= 5:  # Heuristic for "critical"
                adjusted_score *= rp.boost_critical

            # Apply lifecycle penalty
            if r.lifecycle_state.value == "superceded":
                adjusted_score += rp.lifecycle_penalty_superseded
            elif r.lifecycle_state.value == "archived":
                adjusted_score += rp.lifecycle_penalty_archived

            # Filter by min score
            if adjusted_score < rp.min_score:
                continue

            shaped.append(MemoryResult(
                result_id=r.result_id,
                memory_id=r.memory_id,
                memory_type=r.memory_type,
                title=r.title,
                content=r.content,
                score=adjusted_score,
                lifecycle_state=r.lifecycle_state,
                source_event_ids=r.source_event_ids,
                source_memory_ids=r.source_memory_ids,
                confidence=r.confidence,
                reference_count=r.reference_count,
                reasons=r.reasons,
                retrieval_path=r.retrieval_path,
            ))

        # Sort by adjusted score
        shaped.sort(key=lambda x: (-x.score, x.memory_id))

        # Apply limit
        return shaped[:rp.max_results]

    # ── Cache Validation ────────────────────────────────────────────────

    def should_cache(self) -> bool:
        """Check if caching is enabled."""
        return self.policy.cache.enabled

    def cache_key(self, query: MemoryQuery) -> str:
        """Generate a cache key for a query."""
        return f"{query.query_type.value}:{query.text}:{query.project_id or 'global'}"

    def is_cache_valid(self, cache_timestamp: float, current_time: float) -> bool:
        """Check if a cached entry is still valid."""
        cp = self.policy.cache
        if not cp.enabled:
            return False
        age = current_time - cache_timestamp
        if cp.invalidation == CacheInvalidation.TTL:
            return age < cp.ttl_seconds
        if cp.invalidation == CacheInvalidation.LRU:
            return age < cp.max_age_seconds
        return True
