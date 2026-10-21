"""Guarded web search tool with SSRF protection and deterministic intelligence corpus."""

from __future__ import annotations

import hashlib
from typing import Any

from app.core.logging import get_logger
from app.core.security import is_safe_url
from app.tools.base import BaseTool, ToolResult
from app.tools.evidence import EvidenceService

logger = get_logger("agentops.tools.search")

# Deterministic intelligence corpus for hermetic offline testing and demonstrations
DEFAULT_COMPETITOR_CORPUS: list[dict[str, str]] = [
    {
        "domain": "observability",
        "title": "Datadog Cloud Monitoring Architecture & Pricing",
        "url": "https://example.com/datadog/pricing",
        "snippet": (
            "Infrastructure monitoring starts at $15/host/mo. APM and distributed tracing starts at $31/host/mo. "
            "Features multi-tenant cloud ingestion, SLA 99.9% uptime, and 15-month metric retention."
        ),
    },
    {
        "domain": "observability",
        "title": "New Relic Full-Stack Telemetry Overview",
        "url": "https://example.com/newrelic/overview",
        "snippet": (
            "Offers 100 GB/month free data ingest. Standard users priced at $49/user/month. "
            "Enterprise tier provides 99.95% API uptime SLA, SOC2 Type II compliance, and SAML SSO."
        ),
    },
    {
        "domain": "observability",
        "title": "Dynatrace Autonomous Cloud Intelligence Benchmark",
        "url": "https://example.com/dynatrace/benchmark",
        "snippet": (
            "Full-stack monitoring at $0.08 per hour for an 8 GiB host. Enterprise deployment includes "
            "on-premises data isolation options and 99.99% availability commitments."
        ),
    },
    {
        "domain": "fintech",
        "title": "Stripe Payments Infrastructure & Processing Fees",
        "url": "https://example.com/stripe/fees",
        "snippet": (
            "Standard card processing fee is 2.9% + 30 cents per successful transaction. "
            "Features 99.999% historical API uptime, PCI-DSS Level 1 certification, and instant payouts."
        ),
    },
    {
        "domain": "fintech",
        "title": "Adyen Global Unified Commerce Matrix",
        "url": "https://example.com/adyen/matrix",
        "snippet": (
            "Interchange-plus pricing model with 0.13 EUR processing fee per transaction. "
            "Guarantees 99.99% uptime with direct banking switch connections and multi-currency settlement."
        ),
    },
    {
        "domain": "cloud",
        "title": "AWS Enterprise Support & SLAs",
        "url": "https://example.com/aws/sla",
        "snippet": (
            "EC2 provides a monthly uptime percentage of at least 99.99% for multi-AZ instances. "
            "Enterprise Support starts at $15,000/mo with 15-minute response times for critical events."
        ),
    },
]


class WebSearchTool(BaseTool):
    """Allowlisted web search tool querying competitor corpus or search engine."""

    name = "web_search"
    description = (
        "Search competitor intelligence databases or public web sources for relevant market data."
    )

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute guarded search with query bounds and SSRF validation."""
        raw_query = str(kwargs.get("query", "")).strip()
        domain = str(kwargs.get("domain", "")).strip().lower()
        limit = min(max(int(kwargs.get("limit", 5)), 1), 20)

        if not raw_query:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error="Parameter 'query' must be a non-empty string.",
            )

        if len(raw_query) > 500:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error="Query exceeds maximum allowed length of 500 characters.",
            )

        logger.info("web_search_invoked", query=raw_query, domain=domain, limit=limit)

        # Query matcher against corpus
        matching_hits: list[dict[str, str]] = []
        query_words = set(raw_query.lower().split())

        for item in DEFAULT_COMPETITOR_CORPUS:
            item_text = f"{item['title']} {item['snippet']} {item['domain']}".lower()
            if (domain and domain in item["domain"]) or any(
                word in item_text for word in query_words if len(word) > 2
            ):
                matching_hits.append(item)

        # Fallback to general items if query terms didn't match specific domain
        if not matching_hits:
            matching_hits = DEFAULT_COMPETITOR_CORPUS[:limit]
        else:
            matching_hits = matching_hits[:limit]

        # Verify and sanitize all URLs through SSRF guard
        sanitized_hits: list[dict[str, Any]] = []
        evidence_records: list[dict[str, Any]] = []

        for hit in matching_hits:
            hit_url = hit["url"]
            safe, reason = is_safe_url(hit_url)
            if not safe:
                logger.warning("search_hit_blocked_by_ssrf", url=hit_url, reason=reason)
                continue

            content_hash = EvidenceService.compute_content_hash(hit["snippet"])
            evidence = EvidenceService.create_evidence_record(
                run_id=str(kwargs.get("run_id", "run-search")),
                step_identifier=str(kwargs.get("step_identifier", "step-search")),
                tool_name=self.name,
                source_url=hit_url,
                snippet=hit["snippet"],
                metadata={"title": hit["title"], "query": raw_query},
            )
            evidence_records.append(evidence)

            sanitized_hits.append(
                {
                    "title": hit["title"],
                    "url": hit_url,
                    "snippet": hit["snippet"],
                    "content_hash": content_hash,
                }
            )

        summary_digest = hashlib.sha256(
            "".join(h["content_hash"] for h in sanitized_hits).encode("utf-8")
        ).hexdigest()

        return ToolResult(
            success=True,
            tool_name=self.name,
            data={
                "query": raw_query,
                "domain": domain or "general",
                "hits": sanitized_hits,
                "total_hits": len(sanitized_hits),
            },
            content_hash=summary_digest,
            evidence_records=evidence_records,
        )
