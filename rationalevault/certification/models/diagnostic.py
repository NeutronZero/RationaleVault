from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

class Severity(Enum):
    ERROR = auto()
    WARNING = auto()
    INFO = auto()

@dataclass
class Diagnostic:
    id: str
    name: str
    value: Any
    metadata: dict[str, Any] = field(default_factory=dict)
