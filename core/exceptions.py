"""
CYNEXIS — Custom Exceptions
Structured error hierarchy for the entire system.
"""


class CynexisError(Exception):
    """Base exception for all CYNEXIS errors."""

    def __init__(self, message: str = "", code: str = "UNKNOWN"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class SafetyError(CynexisError):
    """Raised when a safety violation is detected."""

    def __init__(self, message: str = "Safety violation"):
        super().__init__(message, code="SAFETY_ERROR")


class HardwareError(CynexisError):
    """Raised when hardware communication fails."""

    def __init__(self, message: str = "Hardware error", device: str = ""):
        self.device = device
        super().__init__(message, code="HARDWARE_ERROR")


class CommandError(CynexisError):
    """Raised when an invalid command is received."""

    def __init__(self, message: str = "Invalid command", command: str = ""):
        self.command = command
        super().__init__(message, code="COMMAND_ERROR")


class ValidationError(CynexisError):
    """Raised when input validation fails."""

    def __init__(self, message: str = "Validation failed", field: str = ""):
        self.field = field
        super().__init__(message, code="VALIDATION_ERROR")


class ConnectionError(CynexisError):
    """Raised when a connection is lost or cannot be established."""

    def __init__(self, message: str = "Connection error", target: str = ""):
        self.target = target
        super().__init__(message, code="CONNECTION_ERROR")


class ActionError(CynexisError):
    """Raised when an action fails to execute."""

    def __init__(self, message: str = "Action failed", action: str = ""):
        self.action = action
        super().__init__(message, code="ACTION_ERROR")
