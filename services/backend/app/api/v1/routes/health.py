"""Health check routes distinguishing liveness from readiness probes."""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_async_session
from app.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Returns 200 OK if the HTTP process is responsive. Does not probe downstream dependencies.",
)
async def liveness_check() -> LivenessResponse:
    """Basic liveness probe."""
    return LivenessResponse(status="alive")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description="Probes database and cache connectivity to determine traffic acceptance readiness.",
)
async def readiness_check(
    response: Response,
    session: AsyncSession = Depends(get_async_session),
) -> ReadinessResponse:
    """Dependency readiness probe testing database and redis."""
    db_status = "unavailable"
    redis_status = "unavailable"
    is_ready = True

    # 1. Probe database
    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        is_ready = False

    # 2. Probe redis
    try:
        client = aioredis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        await client.ping()
        await client.aclose()
        redis_status = "connected"
    except Exception:
        # In mock development mode without redis container running, note disconnected
        redis_status = "disconnected"

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="not_ready",
            database=db_status,
            redis=redis_status,
            app_name=settings.APP_NAME,
            environment=settings.ENVIRONMENT,
        )

    return ReadinessResponse(
        status="ready",
        database=db_status,
        redis=redis_status,
        app_name=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
    )
