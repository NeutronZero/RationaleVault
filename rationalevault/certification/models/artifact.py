from enum import Enum, auto

class ArtifactType(Enum):
    PROJECTION = auto()
    SKILL = auto()
    RUNTIME = auto()
    STORAGE_BACKEND = auto()
    TRANSPORT = auto()
    EMBEDDING_PROVIDER = auto()
    CLI_EXTENSION = auto()
    MCP_EXTENSION = auto()
