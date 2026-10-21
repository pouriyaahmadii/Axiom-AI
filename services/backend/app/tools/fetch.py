"""Guarded document fetching tool enforcing pre-socket SSRF validation, size limits, and MIME filtering."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.logging import get_logger
from app.core.security import is_safe_url
from app.tools.base import BaseTool, ToolResult
from app.tools.evidence import EvidenceService

logger = get_logger("agentops.tools.fetch")

# Allowed MIME content types
ALLOWED_CONTENT_TYPES = {
    "text/html",
    "text/plain",
    "application/json",
    "application/xml",
    "text/markdown",
}

# Maximum byte payload ceiling (1 MB)
DEFAULT_MAX_BYTES = 1_048_576

# Canonical synthetic documents for hermetic offline testing and demonstration domains
SYNTHETIC_DOCUMENTS: dict[str, str] = {
    "https://example.com/datadog/pricing": (
        "Datadog Enterprise Pricing & Infrastructure Overview.\n"
        "Infrastructure monitoring starts at $15 per host monthly. APM tracing is priced at $31 per host monthly. "
        "Standard SLA commits to 99.9% uptime with 15-month telemetry retention. SOC2 Type II and HIPAA compliant."
    ),
    "https://example.com/newrelic/overview": (
        "New Relic Telemetry Platform Specifications.\n"
        "Free tier grants 100 GB/month ingest. Additional users cost $49/user/month. "
        "Production API offers 99.95% uptime SLA, automated incident correlation, and ISO 27001 certification."
    ),
    "https://example.com/dynatrace/benchmark": (
        "Dynatrace Autonomous Cloud Telemetry Benchmark Report.\n"
        "Hourly host pricing begins at $0.08 per 8 GiB memory. Dedicated on-premises deployment available with "
        "99.99% enterprise uptime SLA and granular role-based access control."
    ),
    "https://example.com/stripe/fees": (
        "Stripe Global Payments Infrastructure Whitepaper.\n"
        "Processing fees are 2.9% plus 30 cents per domestic card transaction. "
        "High-availability architecture guarantees 99.999% uptime with PCI Service Provider Level 1 compliance."
    ),
    "https://example.com/features/matrix": (
        "Enterprise Cloud Observability Feature Matrix.\n"
        "Comparison: Full Docker Compose deployment, 99.95% API SLA, transactional outbox durability, "
        "and complete self-hosted data isolation without external telemetry leakage."
    ),
    "https://example.com/benchmark": (
        "Competitive Landscape Analysis & Industry Benchmark.\n"
        "Leading observability platforms document average starter pricing between $15 and $49 per month. "
        "Production SLAs range from 99.9% to 99.999% across tier-1 infrastructure providers."
    ),
}


class FetchDocumentTool(BaseTool):
    """Allowlisted HTTP document retrieval tool with comprehensive security controls."""

    name = "fetch_document"
    description = "Safely retrieve and parse text content from an external URL with strict SSRF, MIME, and size guards."

    @staticmethod
    def _strip_html(raw_html: str) -> str:
        """Sanitize and strip HTML markup to produce readable plain text."""
        # Strip script and style tags completely
        cleaned = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", "", raw_html, flags=re.IGNORECASE)
        # Replace line breaks and paragraph tags with newlines
        cleaned = re.sub(r"<(br|p|div|tr|h[1-6])[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
        # Strip remaining tags
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        # Normalize whitespace
        return re.sub(r"\s+", " ", cleaned).strip()

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute document retrieval enforcing all security and resource constraints."""
        raw_url = str(kwargs.get("url", "")).strip()
        if not raw_url and kwargs.get("domain"):
            domain_slug = str(kwargs.get("domain")).strip().lower()
            raw_url = f"https://example.com/{domain_slug}/pricing"

        timeout_seconds = float(kwargs.get("timeout_seconds", 10.0))
        max_bytes = int(kwargs.get("max_bytes", DEFAULT_MAX_BYTES))

        if not raw_url:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error="Parameter 'url' must be a non-empty string.",
            )

        logger.info("fetch_document_invoked", url=raw_url, max_bytes=max_bytes)

        # 1. Pre-socket SSRF Security Validation
        safe, reason = is_safe_url(raw_url)
        if not safe:
            logger.error("fetch_document_blocked_by_ssrf", url=raw_url, reason=reason)
            return ToolResult(
                success=False,
                tool_name=self.name,
                source_url=raw_url,
                error=f"Security Policy Violation: SSRF protection blocked request to '{raw_url}': {reason}",
            )

        parsed_url = urlparse(raw_url)
        hostname = (parsed_url.hostname or "").lower()

        # 2. Hermetic Offline Handler for RFC 2606 Documentation Domains
        is_rfc2606 = hostname in ("example.com", "example.org", "example.net") or hostname.endswith(
            ".example"
        )
        if is_rfc2606:
            content = SYNTHETIC_DOCUMENTS.get(
                raw_url,
                (
                    f"Verified Documentation for {hostname}: "
                    "Features full offline mock capabilities, multi-database PostgreSQL support, and transactional outbox."
                ),
            )
            content_hash = EvidenceService.compute_content_hash(content)
            evidence = EvidenceService.create_evidence_record(
                run_id=str(kwargs.get("run_id", "run-fetch")),
                step_identifier=str(kwargs.get("step_identifier", "step-fetch")),
                tool_name=self.name,
                source_url=raw_url,
                snippet=content[:500],
                metadata={"status_code": 200, "mime_type": "text/plain", "bytes": len(content)},
            )

            return ToolResult(
                success=True,
                tool_name=self.name,
                source_url=raw_url,
                content_hash=content_hash,
                data={
                    "url": raw_url,
                    "status_code": 200,
                    "content_type": "text/plain",
                    "content": content,
                    "byte_count": len(content),
                    "title": f"Documentation - {hostname}",
                },
                evidence_records=[evidence],
            )

        # 3. Live Safe HTTP Ingestion with Streaming Bounds
        try:
            with (
                httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client,
                client.stream("GET", raw_url) as response,
            ):
                # Check status code
                if response.status_code >= 400:
                    return ToolResult(
                        success=False,
                        tool_name=self.name,
                        source_url=raw_url,
                        error=f"HTTP request failed with status code {response.status_code}",
                    )

                # Validate MIME Content-Type
                content_type = response.headers.get("content-type", "").split(";")[0].strip()
                if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                    return ToolResult(
                        success=False,
                        tool_name=self.name,
                        source_url=raw_url,
                        error=(
                            f"Unsupported content type '{content_type}'. "
                            f"Only safe text and structured formats ({', '.join(sorted(ALLOWED_CONTENT_TYPES))}) are permitted."
                        ),
                    )

                # Check Content-Length if reported
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    return ToolResult(
                        success=False,
                        tool_name=self.name,
                        source_url=raw_url,
                        error=f"Document size ({content_length} bytes) exceeds limit of {max_bytes} bytes.",
                    )

                # Read streamed bytes up to limit
                downloaded_bytes = bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    downloaded_bytes.extend(chunk)
                    if len(downloaded_bytes) > max_bytes:
                        break

                raw_text = downloaded_bytes.decode("utf-8", errors="replace")

            # Extract clean text
            clean_text = self._strip_html(raw_text) if "html" in content_type else raw_text
            content_hash = EvidenceService.compute_content_hash(clean_text)

            evidence = EvidenceService.create_evidence_record(
                run_id=str(kwargs.get("run_id", "run-fetch")),
                step_identifier=str(kwargs.get("step_identifier", "step-fetch")),
                tool_name=self.name,
                source_url=raw_url,
                snippet=clean_text[:500],
                metadata={
                    "status_code": 200,
                    "mime_type": content_type,
                    "bytes": len(clean_text),
                },
            )

            return ToolResult(
                success=True,
                tool_name=self.name,
                source_url=raw_url,
                content_hash=content_hash,
                data={
                    "url": raw_url,
                    "status_code": 200,
                    "content_type": content_type,
                    "content": clean_text,
                    "byte_count": len(clean_text),
                },
                evidence_records=[evidence],
            )

        except httpx.TimeoutException:
            return ToolResult(
                success=False,
                tool_name=self.name,
                source_url=raw_url,
                error=f"Network timeout of {timeout_seconds}s exceeded while fetching '{raw_url}'",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                tool_name=self.name,
                source_url=raw_url,
                error=f"Failed to fetch document '{raw_url}': {exc}",
            )
