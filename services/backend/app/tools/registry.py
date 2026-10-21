"""Strict Tool Registry enforcing allowlists, typed schemas, and audit telemetry."""

from __future__ import annotations

import time
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import SecurityValidationError
from app.core.logging import get_logger
from app.tools.base import BaseTool
from app.tools.compare import CompareEntitiesTool
from app.tools.discover import DiscoverCompetitorsTool
from app.tools.extract import ExtractMetricsTool, ExtractStructuredFactsTool
from app.tools.fetch import FetchApprovedPublicPageTool, FetchDocumentTool
from app.tools.models import ToolMetadata, ToolResult
from app.tools.report import GenerateReportDraftTool
from app.tools.search import SearchPublicWebTool, WebSearchTool

logger = get_logger("agentops.tools.registry")
settings = get_settings()

# Immutable formal allowlist of permitted tool IDs
ALLOWED_TOOL_IDS: frozenset[str] = frozenset(
    {
        # Phase 13 Primary Tool IDs
        "discover_competitors",
        "search_public_web",
        "fetch_approved_public_page",
        "extract_structured_facts",
        "compare_entities",
        "generate_report_draft",
        # Legacy/Backward-Compatible Task Aliases
        "web_search",
        "fetch_document",
        "extract_metrics",
    }
)

# Exported task types alias for agent planner compatibility
ALLOWED_TASK_TYPES: frozenset[str] = ALLOWED_TOOL_IDS


class ToolRegistry:
    """Strict execution registry enforcing allowlists, resource limits, and audit policies.

    Acceptance Criteria:
    - No unregistered tool can ever be executed by the Agent Runtime.
    - Every tool call is validated against typed Pydantic input and output schemas.
    - Resource limits (input size, output size, timeouts) are strictly enforced.
    - Every invocation produces an auditable execution record and SHA-256 content digest.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool[Any, Any]] = {}
        # Register Phase 13 approved tools
        self.register(DiscoverCompetitorsTool())
        self.register(SearchPublicWebTool())
        self.register(FetchApprovedPublicPageTool())
        self.register(ExtractStructuredFactsTool())
        self.register(CompareEntitiesTool())
        self.register(GenerateReportDraftTool())
        # Register backward-compatible aliases
        self.register(WebSearchTool())
        self.register(FetchDocumentTool())
        self.register(ExtractMetricsTool())

    def register(self, tool: BaseTool[Any, Any]) -> None:
        """Register an allowlisted tool instance."""
        if tool.tool_id not in ALLOWED_TOOL_IDS:
            raise SecurityValidationError(
                f"Security policy violation: Tool ID '{tool.tool_id}' is not in the approved allowlist ({', '.join(sorted(ALLOWED_TOOL_IDS))})."
            )
        self._tools[tool.tool_id] = tool
        logger.info(
            "tool_registered_in_sandbox",
            tool_id=tool.tool_id,
            name=tool.name,
            risk_level=tool.metadata.risk_level.value,
        )

    def is_allowed(self, tool_id: str) -> bool:
        """Verify if a tool is registered and within the approved allowlist."""
        return tool_id in ALLOWED_TOOL_IDS and tool_id in self._tools

    def get_tool(self, tool_id: str) -> BaseTool[Any, Any]:
        """Retrieve a registered tool instance or raise SecurityValidationError."""
        if not self.is_allowed(tool_id):
            raise SecurityValidationError(
                f"Security violation: unauthorized tool '{tool_id}' requested. "
                f"Approved tools: {', '.join(sorted(ALLOWED_TOOL_IDS))}."
            )
        return self._tools[tool_id]

    def get_metadata(self, tool_id: str) -> ToolMetadata:
        """Retrieve static metadata and schemas for a registered tool."""
        return self.get_tool(tool_id).metadata

    def list_tools(self) -> list[ToolMetadata]:
        """List metadata for all currently registered tools."""
        return [tool.metadata for tool in self._tools.values()]

    def execute(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        context: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> ToolResult:
        """Safely execute an allowlisted tool within timeout, retry, and schema bounds."""
        start_time = time.perf_counter()

        if not self.is_allowed(tool_name):
            duration = (time.perf_counter() - start_time) * 1000.0
            logger.error("unregistered_tool_execution_blocked", tool_id=tool_name)
            return ToolResult(
                success=False,
                tool_id=tool_name,
                tool_name=tool_name,
                error=(
                    f"Security violation: unauthorized tool '{tool_name}' requested. "
                    f"Approved tools: {', '.join(sorted(ALLOWED_TOOL_IDS))}."
                ),
                duration_ms=round(duration, 2),
            )

        tool = self._tools[tool_name]
        logger.info(
            "executing_sandbox_tool",
            tool_id=tool.tool_id,
            permission_scope=tool.metadata.permission_scope,
            risk_level=tool.metadata.risk_level.value,
        )

        exec_context = dict(context or {})
        if timeout_seconds:
            exec_context["timeout_seconds"] = timeout_seconds

        result = tool.run_validated(raw_params=parameters, context=exec_context)
        return result


# Global singleton registry
_GLOBAL_REGISTRY: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Retrieve the global singleton ToolRegistry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ToolRegistry()
    return _GLOBAL_REGISTRY
