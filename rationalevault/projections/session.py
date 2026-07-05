from dataclasses import dataclass
from typing import Optional, Any, ClassVar
from rationalevault.schema.events import EventRecord
from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer

@dataclass
class SessionSummary:
    session_id: str
    actor: str
    event_count: int
    first_event_at: Optional[str]
    last_event_at: Optional[str]
    event_types_seen: list[str]
    source_event_seqs: list[int]   # provenance: event_sequence values in this session

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "actor": self.actor,
            "event_count": self.event_count,
            "first_event_at": self.first_event_at,
            "last_event_at": self.last_event_at,
            "event_types_seen": self.event_types_seen,
            "source_event_seqs": self.source_event_seqs,
        }


class SessionProjection(BaseProjection):
    """Derives session summaries by grouping events on metadata.session_id."""
    projection_name: ClassVar[str] = "Session"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.BASE
    dependencies: ClassVar[list[type[BaseProjection]]] = []
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 1

    @staticmethod
    def project(events: list[EventRecord]) -> list[SessionSummary]:
        """Returns list ordered by last_event_at DESC. Index 0 = most recent."""
        sessions: dict[str, list[EventRecord]] = {}
        for ev in events:
            if not ev.metadata or not ev.metadata.session_id:
                continue
            sessions.setdefault(ev.metadata.session_id, []).append(ev)

        summaries: list[SessionSummary] = []
        for session_id, evs in sessions.items():
            # sort events in session by sequence
            sorted_evs = sorted(evs, key=lambda e: e.event_sequence)
            actor = sorted_evs[0].metadata.actor if sorted_evs[0].metadata else "unknown"
            event_count = len(sorted_evs)
            
            first_ev = sorted_evs[0]
            last_ev = sorted_evs[-1]
            
            first_event_at = first_ev.recorded_at.isoformat() if first_ev.recorded_at else None
            last_event_at = last_ev.recorded_at.isoformat() if last_ev.recorded_at else None
            
            # keep order of event types seen
            event_types_seen = []
            for e in sorted_evs:
                etype = e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)
                if etype not in event_types_seen:
                    event_types_seen.append(etype)
                    
            source_event_seqs = [e.event_sequence for e in sorted_evs]
            
            summaries.append(SessionSummary(
                session_id=session_id,
                actor=actor,
                event_count=event_count,
                first_event_at=first_event_at,
                last_event_at=last_event_at,
                event_types_seen=event_types_seen,
                source_event_seqs=source_event_seqs
            ))

        # Sort summaries by last_event_at DESC. If last_event_at is None, fallback to max sequence DESC.
        def sort_key(s: SessionSummary) -> tuple[str, int]:
            last_at = s.last_event_at or ""
            max_seq = max(s.source_event_seqs) if s.source_event_seqs else 0
            return (last_at, max_seq)

        summaries.sort(key=sort_key, reverse=True)
        return summaries

    @staticmethod
    def last_session(events: list[EventRecord]) -> Optional[SessionSummary]:
        """Returns the most recently active session."""
        sessions = SessionProjection.project(events)
        return sessions[0] if sessions else None
