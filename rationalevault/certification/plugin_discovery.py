import importlib.metadata
from typing import Dict, Optional, Type

from .models import ArtifactType

class PluginRegistry:
    def __init__(self):
        self._plugins: Dict[str, tuple[Type, ArtifactType]] = {}

    def register(self, name: str, plugin_class: Type, artifact_type: ArtifactType) -> None:
        self._plugins[name] = (plugin_class, artifact_type)

    def discover_entry_points(self) -> None:
        """Scan for python entry points under rationalevault.plugins"""
        try:
            # For Python 3.10+ importlib.metadata
            entry_points = importlib.metadata.entry_points(group="rationalevault.plugins")
        except TypeError:
            # Fallback for older python
            eps = importlib.metadata.entry_points()
            entry_points = eps.get("rationalevault.plugins", [])
            
        for ep in entry_points:
            # Load the plugin
            try:
                plugin_class = ep.load()
                # Guess artifact type from base classes or attributes if not explicitly passed
                # This is a simplification for discovery
                artifact_type = ArtifactType.PROJECTION  # Default guess, ideally defined in plugin metadata
                if hasattr(plugin_class, "__artifact_type__"):
                    artifact_type = plugin_class.__artifact_type__
                    
                self.register(ep.name, plugin_class, artifact_type)
            except Exception:
                pass

    def get_plugin(self, name: str) -> Optional[tuple[Type, ArtifactType]]:
        return self._plugins.get(name)

# Global registry
plugin_registry = PluginRegistry()
