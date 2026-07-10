import yaml
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG = {
    "disable": [],
    "warning_only": False,
    "severity_overrides": {}
}

class CertificationConfig:
    @staticmethod
    def load(config_path: Path) -> Dict[str, Any]:
        if not config_path.exists():
            return DEFAULT_CONFIG.copy()
            
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            
        config = DEFAULT_CONFIG.copy()
        
        # Handle inheritance
        if data.get("extends") == "rationalevault-default":
            pass # already merged by copying DEFAULT_CONFIG
            
        config["disable"].extend(data.get("disable", []))
        config["warning_only"] = data.get("warning_only", False)
        config["severity_overrides"].update(data.get("severity_overrides", {}))
        
        return config
