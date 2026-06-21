from relay.extraction.models import CandidateEvent
from relay.schema.events import EventType


def validate_candidate_event(event: CandidateEvent) -> bool:
    """
    Validates a CandidateEvent's type and payload requirements.
    """
    try:
        # Check event_type is valid
        et = EventType(event.event_type)
    except ValueError:
        return False

    p = event.payload
    if not isinstance(p, dict):
        return False

    # Check required fields by event type
    if et == EventType.PROJECT_CREATED:
        return "name" in p
    elif et == EventType.PROJECT_GOAL_SET:
        return "goal" in p
    elif et == EventType.PROJECT_FOCUS_CHANGED:
        return "focus" in p
    elif et in (EventType.TASK_CREATED, EventType.TASK_MUTATED, EventType.TASK_COMPLETED):
        return "task_id" in p and (et != EventType.TASK_CREATED or "title" in p)
    elif et in (EventType.DECISION_PROPOSED, EventType.DECISION_ACCEPTED, EventType.DECISION_SUPERSEDED):
        return "decision_id" in p and (et != EventType.DECISION_PROPOSED or "title" in p)
    elif et in (EventType.OPEN_QUESTION_RAISED, EventType.OPEN_QUESTION_RESOLVED):
        return "question_id" in p and (et != EventType.OPEN_QUESTION_RAISED or "title" in p)
    elif et == EventType.FACT_RECORDED:
        return "fact_id" in p and "content" in p

    return True
