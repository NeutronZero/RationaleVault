"""Single canonicalization path — all canonicalization flows through here."""

from __future__ import annotations

import unicodedata
from typing import Any

from rationalevault.canonical.specification import UNICODE_NORMALIZATION


def canonicalize(obj: Any) -> Any:
    """Recursively canonicalize any Python object.

    This is the ONLY canonicalization implementation.
    All other modules call this function.

    Rules:
    - Dict keys: sorted lexicographic
    - Strings: NFC normalized
    - Lists: preserve order
    - Ints, floats, bools, None: as-is
    """
    if isinstance(obj, dict):
        return {k: canonicalize(obj[k]) for k in sorted(obj.keys())}
    elif isinstance(obj, str):
        return unicodedata.normalize(UNICODE_NORMALIZATION, obj)
    elif isinstance(obj, list):
        return [canonicalize(item) for item in obj]
    else:
        return obj
