from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VECTORS_DIR = Path(__file__).resolve().parents[3] / "spec" / "vectors" / "ledger"


def load_vectors() -> dict[str, Any]:
    vectors = {}
    if not VECTORS_DIR.exists():
        return vectors
    for path in sorted(VECTORS_DIR.glob("rc-*.json")):
        with path.open("r", encoding="utf-8") as f:
            vectors[path.stem] = json.load(f)
    return vectors


def load_vector(name: str) -> Any:
    path = VECTORS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Ledger compliance vector not found: {name}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
