class RationaleVaultError(Exception):
    """
    Base class for all business-logic exceptions in RationaleVault.
    CLI commands should catch this to display user-friendly error messages
    rather than showing a full stack trace.
    """
    pass

class ConfigurationError(RationaleVaultError):
    """Raised when there is an issue with project configuration or environment setup."""
    pass

class StorageError(RationaleVaultError):
    """Raised when the event store or projection databases encounter an error."""
    pass

class ConcurrencyError(RationaleVaultError):
    """Raised when a lock acquisition fails or a sequence anomaly is detected."""
    pass
