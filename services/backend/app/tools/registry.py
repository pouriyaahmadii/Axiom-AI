"""Guarded tool registry enforcing allowlist policy and execution boundaries."""

from __future__ import annotations

import time
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import SecurityValidationError
from app.tools.base import BaseTool, ToolResult
from app.tools.extract import ExtractMetricsTool
from app.tools.fetch import FetchDocumentTool
from app.tools.search import WebSearchTool

logger = get_logger("agentops.tools.registry")
settings = get_settings()

# Formal allowlist of permitted tool types
ALLOWED_TASK_TYPES: frozenset[str] = frozenset({"web_search", "fetch_document", "extract_metrics"})


class ToolRegistry:
    """Registry coordinating allowlisted tools and enforcing strict execution boundaries."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        # Register default allowlisted tools
        self.register(WebSearchTool())
        self.register(FetchDocumentTool())
        self.register(ExtractMetricsTool())

    def register(self, tool: BaseTool) -> None:
        """Register an allowlisted tool instance."""
        if tool.name not in ALLOWED_TASK_TYPES:
            raise SecurityValidationError(
                f"Security policy violation: Tool '{tool.name}' is not in the approved allowlist ({', '.join(sorted(ALLOWED_TASK_TYPES))})."
            )
        self._tools[tool.name] = tool
        logger.info("tool_registered_in_sandbox", tool_name=tool.name)

    def is_allowed(self, tool_name: str) -> bool:
        """Check if a tool is registered and allowlisted."""
        return tool_name in ALLOWED_TASK_TYPES and tool_name in self._tools

    def get_tool(self, tool_name: str) -> BaseTool:
        """Retrieve an allowlisted tool or raise SecurityValidationError."""
        if not self.is_allowed(tool_name):
            raise SecurityValidationError(
                f"Security violation: unauthorized tool '{tool_name}' requested. "
                f"Approved tools: {', '.join(sorted(ALLOWED_TASK_TYPES))}."
            )
        return self._tools[tool_name]

    def execute(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> ToolResult:
        """Safely execute a tool within allowlist and timeout boundaries."""
        start_time = time.perf_counter()

        if not self.is_allowed(tool_name):
            duration = (time.perf_counter() - start_time) * 1000.0
            logger.error("unauthorized_tool_execution_attempt", tool_name=tool_name)
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=(
                    f"Security violation: unauthorized tool '{tool_name}' requested. "
                    f"Approved tools: {', '.join(sorted(ALLOWED_TASK_TYPES))}."
                ),
                duration_ms=round(duration, 2),
            )

        tool = self._tools[tool_name]
        effective_timeout = timeout_seconds or float(settings.STEP_TIMEOUT_SECONDS)

        logger.info(
            "executing_sandbox_tool",
            tool_name=tool_name,
            timeout_seconds=effective_timeout,
        )

        try:
            # Pass timeout to execution parameters if not explicitly provided
            exec_params = dict(parameters)
            if "timeout_seconds" not in exec_params:
                exec_params["timeout_seconds"] = effective_timeout

            result = tool.run(**exec_params)
            duration = (time.perf_counter() - start_time) * 1000.0
            result.duration_ms = round(duration, 2)
            return result

        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000.0
            logger.error("tool_execution_unhandled_failure", tool_name=tool_name, error=str(exc))
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' failed during execution: {exc}",
                duration_ms=round(duration, 2),
            )


# Global registry singleton
_GLOBAL_REGISTRY: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Retrieve the global singleton ToolRegistry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ToolRegistry()
    return _GLOBAL_REGISTRY
