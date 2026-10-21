"""API v1 master router assembling runs, approvals, and health routes."""

from typing import Any

from fastapi import APIRouter

from app.api.v1.routes.approvals import router as approvals_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.runs import router as runs_router
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()

# Mount child routers
router.include_router(runs_router)
router.include_router(approvals_router)
router.include_router(health_router)


@router.get("/health", tags=["System"], summary="System operational status")
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify service operational status."""
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.LLM_PROVIDER,
        "search_provider": settings.SEARCH_PROVIDER,
    }


@router.get("/info", tags=["System"], summary="Runtime limits and providers")
async def system_info() -> dict[str, Any]:
    """Return runtime constraints and provider configurations."""
    return {
        "app_name": settings.APP_NAME,
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "limits": {
            "max_plan_steps": settings.MAX_PLAN_STEPS,
            "max_execution_seconds": settings.MAX_EXECUTION_SECONDS,
            "step_timeout_seconds": settings.STEP_TIMEOUT_SECONDS,
            "max_retries_per_step": settings.MAX_RETRIES_PER_STEP,
            "budget_usd_limit": settings.BUDGET_USD_LIMIT,
        },
        "providers": {
            "llm": settings.LLM_PROVIDER,
            "search": settings.SEARCH_PROVIDER,
        },
    }


@router.get("/metrics", tags=["Observability"], summary="Operational telemetry metrics")
async def get_metrics_endpoint(format: str = "prometheus") -> Any:
    """Export operational telemetry metrics in Prometheus or structured JSON format."""
    from fastapi.responses import PlainTextResponse

    from app.observability.metrics import metrics

    if format.lower() == "json":
        return metrics.get_summary()

    return PlainTextResponse(
        content=metrics.get_prometheus_format(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
