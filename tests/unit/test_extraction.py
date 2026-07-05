import pytest
from rationalevault.extraction.models import Observation, CandidateEvent
from rationalevault.extraction.extractor import extract_observations
from rationalevault.extraction.suggestor import suggest_events
from rationalevault.extraction.validator import validate_candidate_event


def test_extract_observations_from_json():
    text = """
Some text before.
```json
{
  "observations": [
    {
      "text": "SQLite is selected",
      "confidence": 0.95,
      "source_context": "LLM response details"
    }
  ]
}
```
Some text after.
"""
    obs = extract_observations(text)
    assert len(obs) == 1
    assert obs[0].text == "SQLite is selected"
    assert obs[0].confidence == 0.95
    assert obs[0].source_context == "LLM response details"


def test_extract_observations_fallback_heuristic():
    text = """
- Bullet 1: Decide to use SQLite.
* Bullet 2: Create SQLite models.
1. Bullet 3: Fast API setup.
"""
    obs = extract_observations(text)
    assert len(obs) == 3
    assert obs[0].text == "Bullet 1: Decide to use SQLite."
    assert obs[0].confidence == 0.5
    assert obs[1].text == "Bullet 2: Create SQLite models."
    assert obs[2].text == "Bullet 3: Fast API setup."


def test_suggest_events_from_json():
    text = """
```json
{
  "candidate_events": [
    {
      "event_type": "DECISION_ACCEPTED",
      "stream_id": "decisions",
      "payload": {
        "decision_id": "dec_02"
      },
      "confidence": 0.95,
      "backing_observation": "SQLite is chosen"
    }
  ]
}
```
"""
    events = suggest_events(text)
    assert len(events) == 1
    assert events[0].event_type == "DECISION_ACCEPTED"
    assert events[0].stream_id == "decisions"
    assert events[0].payload == {"decision_id": "dec_02"}
    assert events[0].confidence == 0.95
    assert events[0].backing_observation == "SQLite is chosen"


def test_suggest_events_fallback():
    observations = [
        Observation(text="SQLite selected for local setup", confidence=1.0),
        Observation(text="Resolve database question", confidence=0.8)
    ]
    events = suggest_events("", observations)
    assert len(events) == 2
    assert events[0].event_type == "DECISION_ACCEPTED"
    assert events[1].event_type == "OPEN_QUESTION_RESOLVED"


def test_validate_candidate_event():
    valid_event = CandidateEvent(
        event_type="DECISION_ACCEPTED",
        stream_id="decisions",
        payload={"decision_id": "dec_02"},
        confidence=0.9
    )
    assert validate_candidate_event(valid_event) is True

    invalid_type = CandidateEvent(
        event_type="INVALID_TYPE",
        stream_id="decisions",
        payload={"decision_id": "dec_02"},
        confidence=0.9
    )
    assert validate_candidate_event(invalid_type) is False

    missing_field = CandidateEvent(
        event_type="DECISION_ACCEPTED",
        stream_id="decisions",
        payload={},
        confidence=0.9
    )
    assert validate_candidate_event(missing_field) is False


def test_extract_observations_invalid_json_in_block():
    text = '```json\n{"observations": [{"text": "ok"\n```'
    obs = extract_observations(text)
    assert obs == []


def test_extract_observations_empty_text():
    assert extract_observations("") == []


def test_extract_observations_raw_json_without_code_block():
    text = '{"observations": [{"text": "raw", "confidence": 0.8, "source_context": "direct"}]}'
    obs = extract_observations(text)
    assert len(obs) == 1
    assert obs[0].text == "raw"
    assert obs[0].confidence == 0.8


def test_extract_observations_json_items_missing_text_key():
    text = '```json\n{"observations": [{"confidence": 0.9}]}\n```'
    obs = extract_observations(text)
    assert obs == []


def test_extract_observations_fallback_no_bullets():
    text = "Just plain text with no bullets or dashes."
    obs = extract_observations(text)
    assert obs == []


def test_extract_observations_multiple_json_blocks():
    text = """
```json
{"observations": [{"text": "first"}]}
```
```json
{"observations": [{"text": "second"}]}
```
"""
    obs = extract_observations(text)
    assert len(obs) == 1
    assert obs[0].text == "first"


def test_validate_event_non_dict_payload():
    event = CandidateEvent(event_type="DECISION_ACCEPTED", stream_id="s", payload="not a dict")
    assert validate_candidate_event(event) is False


def test_validate_project_created():
    assert validate_candidate_event(CandidateEvent(event_type="PROJECT_CREATED", stream_id="s", payload={"name": "p"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="PROJECT_CREATED", stream_id="s", payload={})) is False


def test_validate_project_goal_set():
    assert validate_candidate_event(CandidateEvent(event_type="PROJECT_GOAL_SET", stream_id="s", payload={"goal": "g"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="PROJECT_GOAL_SET", stream_id="s", payload={})) is False


def test_validate_project_focus_changed():
    assert validate_candidate_event(CandidateEvent(event_type="PROJECT_FOCUS_CHANGED", stream_id="s", payload={"focus": "f"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="PROJECT_FOCUS_CHANGED", stream_id="s", payload={})) is False


def test_validate_task_created():
    assert validate_candidate_event(CandidateEvent(event_type="TASK_CREATED", stream_id="s", payload={"task_id": "t", "title": "T"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="TASK_CREATED", stream_id="s", payload={"task_id": "t"})) is False
    assert validate_candidate_event(CandidateEvent(event_type="TASK_CREATED", stream_id="s", payload={"title": "T"})) is False


def test_validate_task_mutated():
    assert validate_candidate_event(CandidateEvent(event_type="TASK_MUTATED", stream_id="s", payload={"task_id": "t"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="TASK_MUTATED", stream_id="s", payload={})) is False


def test_validate_task_completed():
    assert validate_candidate_event(CandidateEvent(event_type="TASK_COMPLETED", stream_id="s", payload={"task_id": "t"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="TASK_COMPLETED", stream_id="s", payload={})) is False


def test_validate_decision_proposed():
    assert validate_candidate_event(CandidateEvent(event_type="DECISION_PROPOSED", stream_id="s", payload={"decision_id": "d", "title": "T"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="DECISION_PROPOSED", stream_id="s", payload={"decision_id": "d"})) is False


def test_validate_decision_superseded():
    assert validate_candidate_event(CandidateEvent(event_type="DECISION_SUPERSEDED", stream_id="s", payload={"decision_id": "d"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="DECISION_SUPERSEDED", stream_id="s", payload={})) is False


def test_validate_open_question_raised():
    assert validate_candidate_event(CandidateEvent(event_type="OPEN_QUESTION_RAISED", stream_id="s", payload={"question_id": "q", "title": "T"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="OPEN_QUESTION_RAISED", stream_id="s", payload={"question_id": "q"})) is False


def test_validate_open_question_resolved():
    assert validate_candidate_event(CandidateEvent(event_type="OPEN_QUESTION_RESOLVED", stream_id="s", payload={"question_id": "q"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="OPEN_QUESTION_RESOLVED", stream_id="s", payload={})) is False


def test_validate_fact_recorded():
    assert validate_candidate_event(CandidateEvent(event_type="FACT_RECORDED", stream_id="s", payload={"fact_id": "f", "content": "c"})) is True
    assert validate_candidate_event(CandidateEvent(event_type="FACT_RECORDED", stream_id="s", payload={"fact_id": "f"})) is False
    assert validate_candidate_event(CandidateEvent(event_type="FACT_RECORDED", stream_id="s", payload={"content": "c"})) is False
