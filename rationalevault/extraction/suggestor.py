import json
import re
from typing import Any
from rationalevault.extraction.models import CandidateEvent, Observation


def suggest_events(text: str, observations: list[Observation] = None) -> list[CandidateEvent]:
    """
    Parses candidate events from a text response containing:
    {
      "candidate_events": [
        {
          "event_type": "...",
          "stream_id": "...",
          "payload": {...},
          "confidence": 0.95,
          "backing_observation": "..."
        }
      ]
    }
    If no JSON structure is found, it falls back to parsing from raw observations using heuristics.
    """
    # 1. Search for JSON blocks
    json_blocks = re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)
            if "candidate_events" in data:
                return _parse_candidate_events(data["candidate_events"])
        except json.JSONDecodeError:
            continue

    try:
        data = json.loads(text)
        if "candidate_events" in data:
            return _parse_candidate_events(data["candidate_events"])
    except json.JSONDecodeError:
        pass

    # 2. Heuristic fallback based on observations
    candidates = []
    if observations:
        for obs in observations:
            txt = obs.text.lower()
            if "select" in txt or "decide" in txt or "choose" in txt or "chosen" in txt:
                # E.g., "SQLite selected" -> DECISION_ACCEPTED
                decision_name = obs.text
                candidates.append(CandidateEvent(
                    event_type="DECISION_ACCEPTED",
                    stream_id="decisions",
                    payload={"decision_id": "derived_dec_id", "title": decision_name},
                    confidence=obs.confidence * 0.9,
                    backing_observation=obs.text
                ))
            elif "resolve" in txt or "question resolved" in txt:
                candidates.append(CandidateEvent(
                    event_type="OPEN_QUESTION_RESOLVED",
                    stream_id="questions",
                    payload={"question_id": "derived_q_id", "resolution": obs.text},
                    confidence=obs.confidence * 0.9,
                    backing_observation=obs.text
                ))
            elif "complete" in txt or "done" in txt or "finished" in txt:
                candidates.append(CandidateEvent(
                    event_type="TASK_COMPLETED",
                    stream_id="tasks",
                    payload={"task_id": "derived_task_id"},
                    confidence=obs.confidence * 0.8,
                    backing_observation=obs.text
                ))
    return candidates


def _parse_candidate_events(events_list: list[dict[str, Any]]) -> list[CandidateEvent]:
    res = []
    for item in events_list:
        if isinstance(item, dict) and "event_type" in item and "stream_id" in item:
            res.append(CandidateEvent(
                event_type=str(item["event_type"]),
                stream_id=str(item["stream_id"]),
                payload=dict(item.get("payload", {})),
                confidence=float(item.get("confidence", 1.0)),
                backing_observation=item.get("backing_observation")
            ))
    return res
