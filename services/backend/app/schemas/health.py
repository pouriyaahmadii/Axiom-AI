"""Pydantic schemas for health probes and system readiness."""

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    """Liveness probe indicating that the HTTP process is responsive."""

    status: str = "alive"


class ReadinessResponse(BaseModel):
    """Readiness probe indicating that upstream persistent dependencies are connected."""

    status: str
    database: str
    redis: str
    app_name: str
    environment: str
