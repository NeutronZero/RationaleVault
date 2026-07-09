import logging
import sys

def configure(level: int = logging.INFO) -> None:
    """
    Configure the global logging strategy for RationaleVault.
    This provides a unified format and routes logs appropriately.
    """
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger("rationalevault")
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicate logs if configure is called multiple times
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
        
    root_logger.addHandler(handler)
    
    # Prevent propagation to the root logger which might be configured differently by a host app
    root_logger.propagate = False

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module, ensuring it's a child of the rationalevault namespace.
    Usage: logger = get_logger(__name__)
    """
    if not name.startswith("rationalevault"):
        name = f"rationalevault.{name}"
    return logging.getLogger(name)
