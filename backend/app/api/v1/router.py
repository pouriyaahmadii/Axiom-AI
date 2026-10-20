"""API v1 master router and core health routes."""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint to verify service operational status."""
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.LLM_PROVIDER,
        "search_provider": settings.SEARCH_PROVIDER,
    }


@router.get("/info", tags=["System"])
async def system_info():
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
