"""Log levels for Veltix logger."""

from enum import IntEnum


class LogLevel(IntEnum):
    """
    Log severity levels.

    Levels are ordered by severity, allowing simple filtering:
    - TRACE: Detailed debugging information
    - DEBUG: General debugging information
    - INFO: Informational messages
    - SUCCESS: Successful operations (between INFO and WARNING)
    - WARNING: Warning messages for potential issues
    - ERROR: Error messages for failures
    - CRITICAL: Critical errors requiring immediate attention
    """

    TRACE = 5
    DEBUG = 10
    INFO = 20
    SUCCESS = 25
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    def __str__(self) -> str:
        """Return level name."""
        return self.name
