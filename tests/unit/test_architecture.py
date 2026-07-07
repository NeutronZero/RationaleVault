import pytest
from rationalevault.cli import registry

def test_cli_registry_has_commands():
    """Verify that CLI commands are registered in the centralized registry."""
    assert len(registry.COMMANDS) > 0

def test_cli_main_declarative():
    """Verify that main.py is strictly declarative (no business logic)."""
    with open("rationalevault/cli/main.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Assert main.py doesn't contain command implementations
    assert "def cmd_" not in content
    assert "print(" not in content  # shouldn't handle output formatting directly

def test_cli_utils_no_command_imports():
    """Verify that CLI utilities do not import command implementations, avoiding circular dependencies."""
    import pkgutil
    import importlib
    import sys
    from inspect import getmembers, ismodule
    
    # Force import of all utils modules to trace their imports
    import rationalevault.cli.utils
    for _, module_name, is_pkg in pkgutil.walk_packages(rationalevault.cli.utils.__path__, rationalevault.cli.utils.__name__ + "."):
        mod = importlib.import_module(module_name)
        
        # Check imports inside the module
        for name, member in getmembers(mod):
            if ismodule(member) and "rationalevault.cli.commands" in member.__name__:
                pytest.fail(f"Utility module {module_name} illegally imports command module {member.__name__}")

