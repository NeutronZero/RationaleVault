import json
import re
from typing import Any
from relay.extraction.models import Observation


def extract_observations(text: str) -> list[Observation]:
    """
    Parses observations from text. Searches for JSON blocks containing:
    {
      "observations": [
        {"text": "...", "confidence": 0.9, "source_context": "..."}
      ]
    }
    If no JSON block is found, it attempts to parse the raw text as JSON directly.
    If all parsing fails, it falls back to a simple line-based regex heuristic.
    """
    # 1. Look for markdown code blocks containing JSON
    json_blocks = re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    
    for block in json_blocks:
        try:
            data = json.loads(block)
            if "observations" in data:
                return _parse_observation_list(data["observations"])
        except json.JSONDecodeError:
            continue

    # 2. Try parsing the entire text as JSON
    try:
        data = json.loads(text)
        if "observations" in data:
            return _parse_observation_list(data["observations"])
    except json.JSONDecodeError:
        pass

    # 3. Fallback heuristic: Extract basic bullet points as low-confidence observations
    observations = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Match lines starting with bullet points or dashes
        if line.startswith(("-", "*", "•")) or (line[0].isdigit() and line[1] == "."):
            clean_text = re.sub(r"^[-*•\d\.\s]+", "", line).strip()
            if clean_text:
                observations.append(Observation(
                    text=clean_text,
                    confidence=0.5,
                    source_context="Heuristic bullet point extraction"
                ))

    return observations


def _parse_observation_list(obs_list: list[dict[str, Any]]) -> list[Observation]:
    res = []
    for item in obs_list:
        if isinstance(item, dict) and "text" in item:
            res.append(Observation(
                text=str(item["text"]),
                confidence=float(item.get("confidence", 1.0)),
                source_context=item.get("source_context")
            ))
    return res
