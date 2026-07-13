"""Load compliance vectors from spec/vectors/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VECTORS_DIR = Path(__file__).resolve().parents[3] / "spec" / "vectors"


def load_vectors() -> dict[str, Any]:
    """Load all compliance vectors from spec/vectors/."""
    vectors = {}
    if not VECTORS_DIR.exists():
        return vectors
    for path in VECTORS_DIR.glob("*.json"):
        with path.open("r", encoding="utf-8") as f:
            vectors[path.stem] = json.load(f)
    return vectors


def load_vector(name: str) -> Any:
    """Load a single compliance vector by name."""
    path = VECTORS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Vector not found: {name}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)