from rationalevault.canonical.types import EventType


def test_event_type_is_str_enum():
    assert issubclass(EventType, str)
    assert EventType.DECISION_RECORDED == "decision_recorded"


def test_event_type_members():
    assert EventType.DECISION_RECORDED == "decision_recorded"
    assert EventType.EVALUATION_RECORDED == "evaluation_recorded"
    assert EventType.KNOWLEDGE_UPDATED == "knowledge_updated"


def test_event_type_is_immutable():
    import pytest

    # StrEnum prevents modifying existing members
    with pytest.raises(AttributeError):
        EventType.DECISION_RECORDED = "modified"


def test_event_type_is_hashable():
    s = {EventType.DECISION_RECORDED}
    assert EventType.DECISION_RECORDED in s
