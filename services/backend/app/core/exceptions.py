"""Domain and API exceptions for AgentOps."""

from typing import Any


class AgentOpsError(Exception):
    """Base exception class for all AgentOps domain errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or []


class NotFoundError(AgentOpsError):
    """Raised when a requested resource does not exist."""

    def __init__(
        self, message: str = "Resource not found.", details: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message, code="NOT_FOUND", details=details)


class InvalidStateTransitionError(AgentOpsError):
    """Raised when an illegal or out-of-order state transition is requested."""

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message, code="INVALID_STATE_TRANSITION", details=details)


class ConflictError(AgentOpsError):
    """Raised when an operation conflicts with current state (e.g., duplicate idempotency key)."""

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message, code="CONFLICT", details=details)


class AuthenticationError(AgentOpsError):
    """Raised when request lacks valid authentication or service credentials."""

    def __init__(
        self, message: str = "Authentication required.", details: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message, code="UNAUTHORIZED", details=details)


class ServiceUnavailableError(AgentOpsError):
    """Raised when an upstream dependency (database, redis) is unavailable."""

    def __init__(
        self, message: str = "Service unavailable.", details: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message, code="SERVICE_UNAVAILABLE", details=details)
