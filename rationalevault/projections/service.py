from uuid import UUID
from typing import Optional, Any, Union

from rationalevault.schema.events import EventRecord
from rationalevault.schema.upcaster import UpcasterRegistry
from rationalevault.projections.context import ReplayContext, InterpretiveContext
from rationalevault.projections.pipeline import ReplayPipeline


class ReplayService:
    """
    The canonical query and replay API for RationaleVault.
    
    Provides a unified interface for loading historical event streams from 
    an EventStore database and transforming them through ReplayPipeline 
    (schema resolution, version upcasting, max sequence bounds) before 
    passing them to compilers or projections.
    """

    def __init__(
        self,
        store: Optional[Any] = None,
        registry: Optional[UpcasterRegistry] = None,
        policy_factory: Optional[Any] = None,
    ) -> None:
        if store is None:
            from rationalevault.db.event_store import EventStore
            self._store = EventStore()
        else:
            self._store = store
        self._registry = registry
        self._policy_factory = policy_factory

    def load_project_events(
        self,
        project_id: UUID,
        context: Optional[Union[ReplayContext, InterpretiveContext]] = None,
    ) -> list[EventRecord]:
        """
        Loads project events from the underlying ledger and processes them
        through ReplayPipeline.
        """
        # Resolve target ReplayContext (handling explicit conversion)
        replay_ctx = None
        if context is not None:
            if isinstance(context, InterpretiveContext):
                replay_ctx = context.to_replay_context()
            else:
                replay_ctx = context

        pipeline = ReplayPipeline(replay_ctx, self._registry, self._policy_factory)
        raw_events = self._store.get_project_stream(project_id)
        return pipeline.process(raw_events)
