"""Strict tool registry, allowlisted tools, and evidence provenance services."""

from app.tools.base import BaseTool
from app.tools.citation_auditor import CitationAuditor, CitationAuditResult
from app.tools.compare import CompareEntitiesInput, CompareEntitiesOutput, CompareEntitiesTool
from app.tools.discover import (
    CompetitorEntity,
    DiscoverCompetitorsInput,
    DiscoverCompetitorsOutput,
    DiscoverCompetitorsTool,
)
from app.tools.evidence import EvidenceService
from app.tools.extract import (
    ExtractFactsInput,
    ExtractFactsOutput,
    ExtractMetricsTool,
    ExtractStructuredFactsTool,
)
from app.tools.fetch import (
    FetchApprovedPageInput,
    FetchApprovedPageOutput,
    FetchApprovedPublicPageTool,
    FetchDocumentTool,
)
from app.tools.models import (
    AuditPolicy,
    ResourceLimits,
    RetryPolicy,
    RiskLevel,
    ToolMetadata,
    ToolResult,
)
from app.tools.registry import ALLOWED_TASK_TYPES, ALLOWED_TOOL_IDS, ToolRegistry, get_tool_registry
from app.tools.report import (
    GenerateReportDraftInput,
    GenerateReportDraftOutput,
    GenerateReportDraftTool,
)
from app.tools.search import (
    SearchPublicWebInput,
    SearchPublicWebOutput,
    SearchPublicWebTool,
    WebSearchTool,
)
from app.tools.search_provider import (
    BaseSearchProvider,
    MockSearchProvider,
    SearchHit,
    SearchResult,
    TavilySearchProvider,
    get_search_provider,
    normalize_source_url,
)
from app.tools.security import (
    DOCUMENTATION_DOMAINS,
    SafeHttpClient,
    sanitize_and_envelope_content,
    strip_html_tags,
    validate_url_security,
)

__all__ = [
    "ALLOWED_TASK_TYPES",
    "ALLOWED_TOOL_IDS",
    "AuditPolicy",
    "BaseSearchProvider",
    "BaseTool",
    "CitationAuditResult",
    "CitationAuditor",
    "CompareEntitiesInput",
    "CompareEntitiesOutput",
    "CompareEntitiesTool",
    "CompetitorEntity",
    "DOCUMENTATION_DOMAINS",
    "DiscoverCompetitorsInput",
    "DiscoverCompetitorsOutput",
    "DiscoverCompetitorsTool",
    "EvidenceService",
    "ExtractFactsInput",
    "ExtractFactsOutput",
    "ExtractMetricsTool",
    "ExtractStructuredFactsTool",
    "FetchApprovedPageInput",
    "FetchApprovedPageOutput",
    "FetchApprovedPublicPageTool",
    "FetchDocumentTool",
    "GenerateReportDraftInput",
    "GenerateReportDraftOutput",
    "GenerateReportDraftTool",
    "MockSearchProvider",
    "ResourceLimits",
    "RetryPolicy",
    "RiskLevel",
    "SafeHttpClient",
    "SearchHit",
    "SearchPublicWebInput",
    "SearchPublicWebOutput",
    "SearchPublicWebTool",
    "SearchResult",
    "TavilySearchProvider",
    "ToolMetadata",
    "ToolRegistry",
    "ToolResult",
    "WebSearchTool",
    "get_search_provider",
    "get_tool_registry",
    "normalize_source_url",
    "sanitize_and_envelope_content",
    "strip_html_tags",
    "validate_url_security",
]
