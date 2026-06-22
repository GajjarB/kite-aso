"""TerminalCore error types."""


class TerminalCoreError(RuntimeError):
    """Base error for user-facing terminal failures."""


class ConfigValidationError(TerminalCoreError):
    """Raised when the stored config is missing or invalid."""
