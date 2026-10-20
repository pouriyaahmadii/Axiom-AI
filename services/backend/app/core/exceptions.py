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


class TransientWorkerError(AgentOpsError):
    """Raised for transient worker or external network errors that should be retried with backoff."""

    def __init__(
        self,
        message: str = "Transient failure encountered.",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message, code="TRANSIENT_WORKER_ERROR", details=details)


class DeterministicValidationError(AgentOpsError):
    """Raised when validation, security policy, or domain constraints are deterministically violated."""

    def __init__(
        self,
        message: str = "Deterministic validation failed.",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message, code="DETERMINISTIC_VALIDATION_ERROR", details=details)
