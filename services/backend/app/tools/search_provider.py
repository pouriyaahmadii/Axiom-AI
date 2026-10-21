"""Search provider abstraction layer with deterministic mock and optional live provider."""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.tools.evidence import EvidenceService
from app.tools.security import validate_url_security

logger = get_logger("agentops.tools.search_provider")


class SearchHit(BaseModel):
    """Normalized, deduplicated search result entry."""

    source_id: str = Field(description="Normalized canonical source identifier")
    title: str = Field(description="Page title or excerpt headline")
    url: str = Field(description="Validated public URL")
    snippet: str = Field(description="Verbatim factual excerpt")
    content_hash: str = Field(description="SHA-256 hash of snippet")
    score: float = Field(default=1.0, description="Relevance ranking score")


class SearchResult(BaseModel):
    """Collection of search hits with metadata and provenance."""

    query: str
    hits: list[SearchHit]
    provider: str
    total_hits: int


def normalize_source_url(url: str) -> str:
    """Normalize URL by lowercasing scheme/host and stripping tracking parameters."""
    try:
        parsed = urlparse(url.strip())
        # Filter tracking query parameters
        filtered_query = [
            (k, v)
            for k, v in parse_qsl(parsed.query)
            if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid", "ref")
        ]
        clean_query = urlencode(filtered_query)
        normalized = urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/") or "/",
                parsed.params,
                clean_query,
                "",  # strip fragment
            )
        )
        return normalized
    except Exception:
        return url.strip()


class BaseSearchProvider(ABC):
    """Abstract interface for all search backends."""

    name: str

    @abstractmethod
    def search(self, query: str, domain: str | None = None, limit: int = 5) -> SearchResult:
        """Execute search query and return normalized, deduplicated results."""
        pass


# Curated competitor intelligence corpus for hermetic offline execution
MOCK_CORPUS: list[dict[str, str]] = [
    {
        "domain": "observability",
        "title": "Datadog Cloud Monitoring Architecture & Pricing",
        "url": "https://example.com/datadog/pricing",
        "snippet": (
            "Infrastructure monitoring starts at $15/host/mo. APM distributed tracing starts at $31/host/mo. "
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


class MockSearchProvider(BaseSearchProvider):
    """Deterministic, offline search provider querying seeded competitor corpus."""

    name = "mock"

    def search(self, query: str, domain: str | None = None, limit: int = 5) -> SearchResult:
        """Search local corpus, deduplicating hits and validating safety."""
        clean_query = query.strip()
        clamped_limit = min(max(limit, 1), 20)
        target_domain = (domain or "").strip().lower()

        logger.info(
            "mock_search_query", query=clean_query, domain=target_domain, limit=clamped_limit
        )

        query_tokens = set(re.findall(r"\w+", clean_query.lower()))
        matched_items: list[dict[str, str]] = []

        for item in MOCK_CORPUS:
            item_text = f"{item['title']} {item['snippet']} {item['domain']}".lower()
            if (
                target_domain
                and target_domain in item["domain"].lower()
                or any(token in item_text for token in query_tokens if len(token) > 2)
            ):
                matched_items.append(item)

        if not matched_items:
            matched_items = list(MOCK_CORPUS)

        # Deduplicate hits by normalized URL and content hash
        seen_urls: set[str] = set()
        seen_hashes: set[str] = set()
        hits: list[SearchHit] = []

        for item in matched_items:
            norm_url = normalize_source_url(item["url"])
            safe, _ = validate_url_security(norm_url)
            if not safe:
                continue

            content_hash = EvidenceService.compute_content_hash(item["snippet"])
            if norm_url in seen_urls or content_hash in seen_hashes:
                continue

            seen_urls.add(norm_url)
            seen_hashes.add(content_hash)

            source_id = f"src-{content_hash[:8]}"
            hits.append(
                SearchHit(
                    source_id=source_id,
                    title=item["title"],
                    url=norm_url,
                    snippet=item["snippet"],
                    content_hash=content_hash,
                    score=1.0,
                )
            )
            if len(hits) >= clamped_limit:
                break

        return SearchResult(
            query=clean_query,
            hits=hits,
            provider=self.name,
            total_hits=len(hits),
        )


class TavilySearchProvider(BaseSearchProvider):
    """Optional live search provider integrating the official Tavily Search API.

    API Specifications:
    - Endpoint: https://api.tavily.com/search
    - Authentication: API key via header or JSON payload
    - Terms: Free tier 1,000 monthly requests
    - Active ONLY if TAVILY_API_KEY environment variable is configured.
    """

    name = "tavily"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")

    def search(self, query: str, domain: str | None = None, limit: int = 5) -> SearchResult:
        """Invoke official Tavily API with SSRF filtering and deduplication."""
        if not self.api_key:
            logger.warning("tavily_api_key_missing_falling_back_to_mock")
            return MockSearchProvider().search(query, domain=domain, limit=limit)

        import httpx

        clean_query = f"{query} {domain or ''}".strip()
        clamped_limit = min(max(limit, 1), 10)

        payload = {
            "api_key": self.api_key,
            "query": clean_query,
            "search_depth": "basic",
            "max_results": clamped_limit,
            "include_raw_content": False,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post("https://api.tavily.com/search", json=payload)
                if res.status_code != 200:
                    logger.error("tavily_api_error", status_code=res.status_code, body=res.text)
                    return MockSearchProvider().search(query, domain=domain, limit=limit)

                raw_data = res.json()
                raw_results = raw_data.get("results", [])

            hits: list[SearchHit] = []
            seen_urls: set[str] = set()

            for item in raw_results:
                raw_url = item.get("url", "")
                norm_url = normalize_source_url(raw_url)

                # Screen external URL with strict SSRF validator
                safe, reason = validate_url_security(norm_url)
                if not safe:
                    logger.warning("tavily_result_url_blocked", url=norm_url, reason=reason)
                    continue

                if norm_url in seen_urls:
                    continue
                seen_urls.add(norm_url)

                snippet = item.get("content", "").strip()
                content_hash = EvidenceService.compute_content_hash(snippet)
                source_id = f"src-{content_hash[:8]}"

                hits.append(
                    SearchHit(
                        source_id=source_id,
                        title=item.get("title", "Search Result"),
                        url=norm_url,
                        snippet=snippet,
                        content_hash=content_hash,
                        score=float(item.get("score", 1.0)),
                    )
                )

            return SearchResult(
                query=clean_query,
                hits=hits,
                provider=self.name,
                total_hits=len(hits),
            )

        except Exception as exc:
            logger.error("tavily_search_failed", error=str(exc))
            # Safe degradation to mock provider on network or API failures
            return MockSearchProvider().search(query, domain=domain, limit=limit)


def get_search_provider(provider_name: str | None = None) -> BaseSearchProvider:
    """Factory selecting the active search provider."""
    env_provider = os.getenv("SEARCH_PROVIDER") or "mock"
    selected = (provider_name or env_provider).lower()
    if selected == "tavily" and os.getenv("TAVILY_API_KEY"):
        return TavilySearchProvider()
    return MockSearchProvider()
