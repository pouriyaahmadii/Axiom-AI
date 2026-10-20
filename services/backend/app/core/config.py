"""Application settings and configuration management."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core application settings with environment variable overrides."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Application Environment
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    APP_NAME: str = Field(default="AgentOps", description="Application name")
    DEBUG: bool = Field(default=False, description="Debug mode")
    API_HOST: str = Field(default="127.0.0.1", description="API binding host")
    API_PORT: int = Field(default=8000, description="API binding port")
    API_V1_PREFIX: str = Field(default="/api/v1", description="API v1 prefix")
    CORS_ORIGINS: list[str] = Field(
        default=["http://127.0.0.1:3000", "http://localhost:3000"],
        description="Allowed CORS origins",
    )
    SECRET_KEY: str = Field(
        default="change-me-in-production-use-a-strong-secret-key-at-least-32-chars",
        description="Application secret key",
    )
    API_KEY: str = Field(
        default="agentops-dev-internal-key",
        description="Internal service API key for API clients and n8n",
    )

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://agentops_user:agentops_pass@127.0.0.1:5432/agentops_db",
        description="Async PostgreSQL connection string",
    )
    SYNC_DATABASE_URL: str = Field(
        default="postgresql://agentops_user:agentops_pass@127.0.0.1:5432/agentops_db",
        description="Sync PostgreSQL connection string for migrations/Celery",
    )

    # Redis & Celery
    REDIS_URL: str = Field(default="redis://127.0.0.1:6379/0", description="Redis connection URL")
    CELERY_BROKER_URL: str = Field(
        default="redis://127.0.0.1:6379/1", description="Celery broker URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://127.0.0.1:6379/2", description="Celery result backend URL"
    )

    # Model & Provider Configuration
    LLM_PROVIDER: str = Field(
        default="mock", description="LLM provider: 'mock', 'openai', or 'ollama'"
    )
    SEARCH_PROVIDER: str = Field(
        default="mock", description="Search provider: 'mock', 'tavily', or 'duckduckgo'"
    )
    MOCK_DETERMINISTIC_SEED: int = Field(
        default=42, description="Random seed for deterministic mock operations"
    )

    # Optional External Providers
    OPENAI_API_KEY: str | None = Field(default=None, description="Optional OpenAI API key")
    OPENAI_MODEL_NAME: str = Field(default="gpt-4o-mini", description="OpenAI model identifier")
    OLLAMA_BASE_URL: str = Field(
        default="http://127.0.0.1:11434", description="Ollama API base URL"
    )
    OLLAMA_MODEL_NAME: str = Field(default="llama3.2", description="Ollama model identifier")
    TAVILY_API_KEY: str | None = Field(default=None, description="Optional Tavily API key")

    # Safety Bounds & Execution Limits
    MAX_PLAN_STEPS: int = Field(
        default=10, ge=1, le=50, description="Maximum allowable steps in an execution plan"
    )
    MAX_EXECUTION_SECONDS: int = Field(
        default=300, ge=10, le=1800, description="Global timeout for run execution"
    )
    STEP_TIMEOUT_SECONDS: int = Field(
        default=60, ge=5, le=300, description="Per-step execution timeout"
    )
    MAX_RETRIES_PER_STEP: int = Field(
        default=2, ge=0, le=5, description="Maximum automated retries per failed step"
    )
    BUDGET_USD_LIMIT: float = Field(default=1.00, ge=0.0, description="Cost budget limit in USD")

    # Observability & Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format: 'json' or 'console'")
    OTEL_ENABLED: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://127.0.0.1:4317", description="OTLP exporter endpoint"
    )

    # Automation & Integration
    N8N_WEBHOOK_URL: str | None = Field(
        default=None, description="Optional n8n notification webhook URL"
    )
    N8N_WEBHOOK_SECRET: str | None = Field(
        default=None, description="Optional secret for n8n HMAC signing"
    )


@lru_cache
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()
