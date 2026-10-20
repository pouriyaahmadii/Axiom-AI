"""Domain enumerations for AgentOps execution states, events, and statuses."""

from enum import Enum


class RunStatus(str, Enum):
    """Lifecycle status of a research or analysis run."""

    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ABORTED_BY_OPERATOR = "ABORTED_BY_OPERATOR"


class StepStatus(str, Enum):
    """Execution status of an individual plan step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ApprovalStatus(str, Enum):
    """Status of a human-in-the-loop approval gate."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ToolInvocationStatus(str, Enum):
    """Outcome status of an allowlisted tool invocation."""

    INVOKED = "INVOKED"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"


class LLMCallStatus(str, Enum):
    """Outcome status of an external model inference call."""

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


class OutboxStatus(str, Enum):
    """Delivery status of a transactional outbox notification message."""

    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class AuditEventType(str, Enum):
    """Standardized audit and observability event classifications."""

    RUN_QUEUED = "RUN_QUEUED"
    PLAN_SYNTHESIZED = "PLAN_SYNTHESIZED"
    PLAN_VALIDATED = "PLAN_VALIDATED"
    STEP_STARTED = "STEP_STARTED"
    TOOL_CALLED = "TOOL_CALLED"
    EVIDENCE_CAPTURED = "EVIDENCE_CAPTURED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_RESOLVED = "APPROVAL_RESOLVED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_RETRYING = "STEP_RETRYING"
    STEP_FAILED = "STEP_FAILED"
    REPORT_SYNTHESIZED = "REPORT_SYNTHESIZED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
