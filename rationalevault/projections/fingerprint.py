from __future__ import annotations
import hashlib
from typing import Optional
from rationalevault.projections.base import SemVer
from rationalevault.schema.events import EventRecord
from rationalevault.knowledge.models import KnowledgeObject

def compute_event_stream_fingerprint(events: list[EventRecord], project_id: str, version: SemVer) -> str:
    """Computes a deterministic fingerprint of an event stream for a project."""
    event_count = len(events)
    if event_count == 0:
        max_sequence = 0
        last_recorded_at = ""
    else:
        max_sequence = max(e.event_sequence for e in events)
        # Find the last recorded time
        recorded_times = [e.recorded_at for e in events if e.recorded_at is not None]
        last_recorded_at = max(recorded_times).isoformat() if recorded_times else ""

    payload = f"event_stream|{version}|{project_id}|{event_count}|{max_sequence}|{last_recorded_at}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def compute_knowledge_fingerprint(knowledge: list[KnowledgeObject], project_id: str, version: SemVer) -> str:
    """Computes a deterministic fingerprint of raw knowledge state."""
    # Canonicalize by sorting knowledge items by ID and version
    sorted_items = sorted(knowledge, key=lambda k: (k.id or "", k.version or 0))
    kv_pairs = [f"{k.id}:{k.version}" for k in sorted_items]
    payload = f"knowledge_store|{version}|{project_id}|" + ",".join(kv_pairs)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def compute_composite_fingerprint(
    version: SemVer,
    dependency_fingerprints: dict[str, str],
    raw_input_hash: Optional[str] = None
) -> str:
    """Computes a deterministic fingerprint combining dependency state and optional inputs."""
    # Canonicalize dependencies sorting by projection name
    sorted_deps = sorted(dependency_fingerprints.items())
    dep_str = ",".join(f"{name}:{fp}" for name, fp in sorted_deps)
    
    payload = f"composite|{version}|{dep_str}|{raw_input_hash or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
