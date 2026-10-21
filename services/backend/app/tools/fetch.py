"""Tool: fetch_approved_public_page - Safely fetches approved web pages with SSRF and redirect guards."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import SecurityValidationError
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
from app.tools.security import (
    DOCUMENTATION_DOMAINS,
    SafeHttpClient,
    sanitize_and_envelope_content,
    strip_html_tags,
    validate_url_security,
)

logger = get_logger("agentops.tools.fetch")


class FetchApprovedPageInput(BaseModel):
    """Input payload for fetching an approved public page."""

    model_config = ConfigDict(extra="ignore")

    url: str = Field(default="", description="Target HTTP or HTTPS URL to retrieve")
    domain: str | None = Field(
        default=None, description="Expected domain classification for validation"
    )
    approved_source_urls: list[str] = Field(
        default_factory=list,
        description="Allowlist of URLs discovered during search or confirmed by operator",
    )
    timeout_seconds: float = Field(
        default=10.0, ge=1.0, le=60.0, description="Network timeout in seconds"
    )
    max_bytes: int = Field(
        default=1_048_576, ge=1024, le=5_242_880, description="Max response size in bytes"
    )


class FetchApprovedPageOutput(BaseModel):
    """Normalized, sanitized page fetch output schema."""

    url: str
    final_url: str
    status_code: int
    content_type: str
    content: str = Field(description="Untrusted enveloped text demarcated against prompt injection")
    sanitized_text: str = Field(description="Clean plain text without markup")
    content_hash: str = Field(description="SHA-256 hash of plain text")
    byte_count: int
    redirect_chain: list[str] = Field(default_factory=list)
    evidence_records: list[dict[str, Any]] = Field(default_factory=list)


class FetchApprovedPublicPageTool(BaseTool[FetchApprovedPageInput, FetchApprovedPageOutput]):
    """Allowlisted tool retrieving external public documents with end-to-end security guards."""

    metadata = ToolMetadata(
        tool_id="fetch_approved_public_page",
        name="Fetch Approved Public Page",
        description=(
            "Safely fetch and parse text from an approved public web page with strict pre-socket SSRF, "
            "port restrictions, manual redirect hop evaluation, and prompt-injection envelope protection."
        ),
        input_schema=FetchApprovedPageInput,
        output_schema=FetchApprovedPageOutput,
        timeout_seconds=20.0,
        retry_policy=RetryPolicy(max_retries=1, backoff_factor_seconds=1.0),
        risk_level=RiskLevel.MEDIUM,
        requires_approval=False,
        permission_scope="research:read",
        resource_limits=ResourceLimits(max_input_length=2000, max_output_bytes=1_048_576),
        audit_policy=AuditPolicy(audit_event_type="DOCUMENT_FETCH"),
    )

    @staticmethod
    def _strip_html(raw_html: str) -> str:
        """Sanitize and strip HTML markup to produce readable plain text."""
        return strip_html_tags(raw_html)

    def execute(
        self,
        input_data: FetchApprovedPageInput,
        context: dict[str, Any] | None = None,
    ) -> FetchApprovedPageOutput:
        """Execute document retrieval enforcing all boundary and provenance rules."""
        raw_url = input_data.url.strip()
        ctx = context or {}
        run_id = str(ctx.get("run_id", "run-fetch"))
        step_id = str(ctx.get("step_identifier", "step-fetch"))

        # Fallback if URL is blank but domain is provided
        if not raw_url and input_data.domain:
            raw_url = f"https://example.com/{input_data.domain.lower().strip()}/pricing"

        if not raw_url:
            raise SecurityValidationError("Target URL must be a non-empty string.")

        logger.info("fetching_approved_page", url=raw_url, max_bytes=input_data.max_bytes)

        # 1. Pre-Socket SSRF & URL Security Validation
        safe, failure_reason = validate_url_security(raw_url)
        if not safe:
            logger.error("fetch_blocked_by_security_policy", url=raw_url, reason=failure_reason)
            raise SecurityValidationError(f"SSRF Security Violation: {failure_reason}")

        # 2. Origin Verification against Approved Sources
        # Protects against model hallucinating arbitrary ungrounded URLs
        parsed = urlparse(raw_url)
        hostname = (parsed.hostname or "").lower()

        # Documentation domains for hermetic testing are always pre-approved
        is_preapproved = hostname in DOCUMENTATION_DOMAINS or hostname.endswith(".example")

        if not is_preapproved and input_data.approved_source_urls:
            # Check if target URL or domain matches one of the approved sources
            approved_hosts = {
                (urlparse(u).hostname or "").lower() for u in input_data.approved_source_urls
            }
            if hostname not in approved_hosts and raw_url not in input_data.approved_source_urls:
                raise SecurityValidationError(
                    f"URL '{raw_url}' is not in the approved sources list ({', '.join(sorted(approved_hosts))})."
                )

        # 3. Safe HTTP Ingestion with Manual Redirect Hop Inspection
        client = SafeHttpClient(
            connect_timeout_seconds=min(5.0, input_data.timeout_seconds),
            total_timeout_seconds=input_data.timeout_seconds,
            max_bytes=input_data.max_bytes,
            max_redirects=3,
        )
        fetch_res = client.fetch_url(raw_url)

        # 4. Content Sanitization & Untrusted Envelope (Prompt Injection Defense)
        raw_text = fetch_res["text"]
        sanitized_plain = strip_html_tags(raw_text)
        enveloped_content = sanitize_and_envelope_content(
            raw_text=raw_text,
            source_url=fetch_res["final_url"],
            max_chars=50_000,
        )

        content_hash = EvidenceService.compute_content_hash(sanitized_plain)

        # 5. Build Cryptographic Evidence Record
        evidence = EvidenceService.create_evidence_record(
            run_id=run_id,
            step_identifier=step_id,
            tool_name=self.tool_id,
            source_url=fetch_res["final_url"],
            snippet=sanitized_plain[:500],
            metadata={
                "status_code": fetch_res["status_code"],
                "content_type": fetch_res["content_type"],
                "byte_count": fetch_res["byte_count"],
                "redirect_hops": len(fetch_res.get("redirect_chain", [])),
            },
        )

        return FetchApprovedPageOutput(
            url=raw_url,
            final_url=fetch_res["final_url"],
            status_code=fetch_res["status_code"],
            content_type=fetch_res["content_type"],
            content=enveloped_content,
            sanitized_text=sanitized_plain,
            content_hash=content_hash,
            byte_count=fetch_res["byte_count"],
            redirect_chain=fetch_res.get("redirect_chain", []),
            evidence_records=[evidence],
        )


# Backward-compatible alias for existing agent runtime
class FetchDocumentTool(FetchApprovedPublicPageTool):
    """Backward-compatible alias for 'fetch_document'."""

    metadata = ToolMetadata(
        tool_id="fetch_document",
        name="Fetch Document",
        description="Safely fetch and parse text from external web sources (legacy alias).",
        input_schema=FetchApprovedPageInput,
        output_schema=FetchApprovedPageOutput,
        timeout_seconds=20.0,
        retry_policy=RetryPolicy(max_retries=1, backoff_factor_seconds=1.0),
        risk_level=RiskLevel.MEDIUM,
        requires_approval=False,
        permission_scope="research:read",
        resource_limits=ResourceLimits(max_input_length=2000, max_output_bytes=1_048_576),
        audit_policy=AuditPolicy(audit_event_type="DOCUMENT_FETCH"),
    )
