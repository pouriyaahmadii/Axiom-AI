"""Structured logging setup for AgentOps."""

import logging
import sys
from typing import Any


def setup_logging(level: str = "INFO", log_format: str = "json") -> None:
    """Configure system-wide structured logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    try:
        import structlog

        shared_processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]

        if log_format.lower() == "json":
            renderer = structlog.processors.JSONRenderer()
        else:
            renderer = structlog.dev.ConsoleRenderer(colors=True)

        structlog.configure(
            processors=shared_processors
            + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                foreign_pre_chain=shared_processors,
                processor=renderer,
            )
        )

        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)

    except ImportError:
        # Fallback to standard logging format if structlog is unavailable
        fmt = (
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
            if log_format.lower() == "json"
            else "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        logging.basicConfig(level=log_level, format=fmt, stream=sys.stdout, force=True)


def get_logger(name: str = "agentops") -> Any:
    """Get a structured logger instance."""
    try:
        import structlog

        return structlog.get_logger(name)
    except ImportError:
        return logging.getLogger(name)
