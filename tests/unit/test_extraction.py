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
