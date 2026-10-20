"""Main FastAPI application factory and entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.security import SecurityValidationError

settings = get_settings()
logger = get_logger("agentops.main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan context manager for startup and shutdown routines."""
    setup_logging(level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger.info(
        "Application starting up",
        app_name=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        llm_provider=settings.LLM_PROVIDER,
        search_provider=settings.SEARCH_PROVIDER,
    )
    yield
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Maintainable, secure-by-default, observable AI Agent Operations Platform",
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Security exception handler
    @app.exception_handler(SecurityValidationError)
    async def security_exception_handler(request: Request, exc: SecurityValidationError):
        logger.warning(
            "Security policy violation intercepted", path=request.url.path, error=str(exc)
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Security policy violation", "message": str(exc)},
        )

    # Register API v1 routes
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # Root endpoint
    @app.get("/", tags=["System"])
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": "0.1.0",
            "environment": settings.ENVIRONMENT,
            "docs": "/docs"
            if settings.DEBUG or settings.ENVIRONMENT != "production"
            else "disabled",
        }

    return app


app = create_app()
