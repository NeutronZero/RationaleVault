from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ExtensionManifest:
    name: str
    version: str
    description: str
    author: str
    license: str
    api_version: str
    supported_rationalevault: str  # PEP 440 specifier
    entry_points: dict[str, list[str]] = field(default_factory=dict)
    homepage: Optional[str] = None
    repository: Optional[str] = None
    documentation: Optional[str] = None
