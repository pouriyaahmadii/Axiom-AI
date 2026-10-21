"""Main FastAPI application factory and entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_v1_router
from app.api.v1.routes.health import router as health_router
from app.core.config import get_settings
from app.core.exceptions import (
    AgentOpsError,
    AuthenticationError,
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.logging import get_logger, setup_logging
from app.core.middleware import CorrelationIdMiddleware
from app.core.security import SecurityValidationError

settings = get_settings()
logger = get_logger("agentops.main")


def make_error_response(
    status_code: int,
    code: str,
    message: str,
    correlation_id: str | None = None,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Construct a standardized error response envelope adhering to docs/13-api-design.md."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "correlation_id": correlation_id,
                "details": details or [],
            }
        },
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown routines."""
    setup_logging(level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    from app.observability.tracer import init_tracer

    init_tracer()
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

    # Middleware registration
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register root health probes
    app.include_router(health_router)

    # Register API v1 routes
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # Exception Handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        details = []
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err.get("loc", []) if loc != "body")
            details.append({"field": field or None, "issue": err.get("msg", "Validation error")})
        return make_error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request payload failed schema validation.",
            correlation_id=correlation_id,
            details=details,
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        return make_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code=exc.code,
            message=exc.message,
            correlation_id=correlation_id,
            details=exc.details,
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_state_transition_handler(
        request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        return make_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code=exc.code,
            message=exc.message,
            correlation_id=correlation_id,
            details=exc.details,
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        return make_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code=exc.code,
            message=exc.message,
            correlation_id=correlation_id,
            details=exc.details,
        )

    @app.exception_handler(AuthenticationError)
    async def auth_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        return make_error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=exc.code,
            message=exc.message,
            correlation_id=correlation_id,
            details=exc.details,
        )

    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_handler(
        request: Request, exc: ServiceUnavailableError
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        return make_error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=exc.code,
            message=exc.message,
            correlation_id=correlation_id,
            details=exc.details,
        )

    @app.exception_handler(SecurityValidationError)
    async def security_exception_handler(
        request: Request, exc: SecurityValidationError
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        logger.warning(
            "Security policy violation intercepted", path=request.url.path, error=str(exc)
        )
        return make_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="SECURITY_VIOLATION",
            message=str(exc),
            correlation_id=correlation_id,
        )

    @app.exception_handler(AgentOpsError)
    async def agentops_error_handler(request: Request, exc: AgentOpsError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        return make_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=exc.code,
            message=exc.message,
            correlation_id=correlation_id,
            details=exc.details,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        logger.error(
            "Unhandled server exception intercepted",
            path=request.url.path,
            error=str(exc),
            exc_info=True,
        )
        return make_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred. Please contact the administrator.",
            correlation_id=correlation_id,
        )

    # Root endpoint
    @app.get("/", tags=["System"])
    async def root() -> dict[str, str]:
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
