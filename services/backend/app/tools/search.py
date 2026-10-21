"""Tool: search_public_web - Searches external sources with deduplication and SSRF guards."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.logging import get_logger
from app.tools.base import BaseTool
from app.tools.evidence import EvidenceService
from app.tools.models import (
    AuditPolicy,
    ResourceLimits,
    RetryPolicy,
    RiskLevel,
    ToolMetadata,
)
from app.tools.search_provider import SearchHit, get_search_provider

logger = get_logger("agentops.tools.search")


class SearchPublicWebInput(BaseModel):
    """Input payload for public web and competitor search."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(min_length=1, max_length=500, description="Natural language search query")
    domain: str | None = Field(default=None, description="Optional domain or market sector filter")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum search hits to return")


class SearchPublicWebOutput(BaseModel):
    """Normalized, deduplicated search results schema."""

    query: str
    hits: list[SearchHit]
    total_hits: int
    search_provider: str
    evidence_records: list[dict[str, Any]] = Field(default_factory=list)


class SearchPublicWebTool(BaseTool[SearchPublicWebInput, SearchPublicWebOutput]):
    """Allowlisted tool executing public web search using active SearchProvider."""

    metadata = ToolMetadata(
        tool_id="search_public_web",
        name="Search Public Web",
        description="Search public web and competitor intelligence sources with URL deduplication and SSRF filtering.",
        input_schema=SearchPublicWebInput,
        output_schema=SearchPublicWebOutput,
        timeout_seconds=15.0,
        retry_policy=RetryPolicy(max_retries=2, backoff_factor_seconds=1.0),
        risk_level=RiskLevel.MEDIUM,
        requires_approval=False,
        permission_scope="research:read",
        resource_limits=ResourceLimits(max_input_length=1000, max_output_bytes=524_288),
        audit_policy=AuditPolicy(audit_event_type="PUBLIC_WEB_SEARCH"),
    )

    def execute(
        self,
        input_data: SearchPublicWebInput,
        context: dict[str, Any] | None = None,
    ) -> SearchPublicWebOutput:
        """Execute search using provider and convert results into evidence records."""
        ctx = context or {}
        run_id = str(ctx.get("run_id", "run-search"))
        step_id = str(ctx.get("step_identifier", "step-search"))
        provider_name = ctx.get("search_provider")

        provider = get_search_provider(provider_name)
        search_res = provider.search(
            query=input_data.query,
            domain=input_data.domain,
            limit=input_data.limit,
        )

        evidence_records: list[dict[str, Any]] = []
        for hit in search_res.hits:
            ev = EvidenceService.create_evidence_record(
                run_id=run_id,
                step_identifier=step_id,
                tool_name=self.tool_id,
                source_url=hit.url,
                snippet=hit.snippet,
                metadata={"title": hit.title, "source_id": hit.source_id, "score": hit.score},
            )
            evidence_records.append(ev)

        return SearchPublicWebOutput(
            query=search_res.query,
            hits=search_res.hits,
            total_hits=search_res.total_hits,
            search_provider=search_res.provider,
            evidence_records=evidence_records,
        )


# Backward-compatible alias for existing agent runtime
class WebSearchTool(SearchPublicWebTool):
    """Backward-compatible alias for 'web_search'."""

    metadata = ToolMetadata(
        tool_id="web_search",
        name="Web Search",
        description="Search public web and competitor intelligence sources (legacy alias).",
        input_schema=SearchPublicWebInput,
        output_schema=SearchPublicWebOutput,
        timeout_seconds=15.0,
        retry_policy=RetryPolicy(max_retries=2, backoff_factor_seconds=1.0),
        risk_level=RiskLevel.MEDIUM,
        requires_approval=False,
        permission_scope="research:read",
        resource_limits=ResourceLimits(max_input_length=1000, max_output_bytes=524_288),
        audit_policy=AuditPolicy(audit_event_type="PUBLIC_WEB_SEARCH"),
    )
