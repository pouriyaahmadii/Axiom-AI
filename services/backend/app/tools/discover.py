"""Tool: discover_competitors - Identifies leading market entities and competitor targets."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

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

logger = get_logger("agentops.tools.discover")


class DiscoverCompetitorsInput(BaseModel):
    """Input payload for competitor discovery."""

    domain: str = Field(
        min_length=2, max_length=100, description="Target industry or market domain"
    )
    geography: str | None = Field(
        default=None, description="Geographic scope (e.g., North America, Global)"
    )
    max_results: int = Field(
        default=5, ge=1, le=20, description="Maximum competitor entities to discover"
    )


class CompetitorEntity(BaseModel):
    """Structured entity representing an identified competitor."""

    name: str = Field(description="Commercial name of the competitor organization or product")
    domain: str = Field(description="Market sector classification")
    description: str = Field(description="Summary of primary offering and architecture")
    primary_url: str = Field(description="Verified canonical public documentation or website URL")
    market_tier: str = Field(default="tier-1", description="Market classification tier")


class DiscoverCompetitorsOutput(BaseModel):
    """Output schema for competitor discovery."""

    domain: str
    geography: str
    competitors: list[CompetitorEntity]
    total_found: int
    evidence_records: list[dict[str, Any]] = Field(default_factory=list)


# Seeded domain knowledge directory for deterministic discovery
KNOWN_DOMAIN_ENTITIES: dict[str, list[dict[str, str]]] = {
    "cloud-observability": [
        {
            "name": "Datadog",
            "domain": "cloud-observability",
            "description": "SaaS infrastructure monitoring, application performance monitoring (APM), and log management.",
            "primary_url": "https://example.com/datadog/pricing",
            "market_tier": "tier-1",
        },
        {
            "name": "New Relic",
            "domain": "cloud-observability",
            "description": "All-in-one observability platform with generous free data ingest and telemetry correlation.",
            "primary_url": "https://example.com/newrelic/overview",
            "market_tier": "tier-1",
        },
        {
            "name": "Dynatrace",
            "domain": "cloud-observability",
            "description": "Enterprise autonomous cloud intelligence with Davis AI engine and automated root-cause analysis.",
            "primary_url": "https://example.com/dynatrace/benchmark",
            "market_tier": "tier-1",
        },
    ],
    "fintech": [
        {
            "name": "Stripe",
            "domain": "fintech",
            "description": "Global payment gateway and developer platform for online commerce and billing infrastructure.",
            "primary_url": "https://example.com/stripe/fees",
            "market_tier": "tier-1",
        },
        {
            "name": "Adyen",
            "domain": "fintech",
            "description": "End-to-end payments platform connecting businesses directly to global card networks and banking rails.",
            "primary_url": "https://example.com/adyen/matrix",
            "market_tier": "tier-1",
        },
    ],
}


class DiscoverCompetitorsTool(BaseTool[DiscoverCompetitorsInput, DiscoverCompetitorsOutput]):
    """Allowlisted tool discovering relevant competitor entities in a target industry."""

    metadata = ToolMetadata(
        tool_id="discover_competitors",
        name="Discover Competitors",
        description="Discover candidate competitor organizations and market entities within a target industry domain.",
        input_schema=DiscoverCompetitorsInput,
        output_schema=DiscoverCompetitorsOutput,
        timeout_seconds=10.0,
        retry_policy=RetryPolicy(max_retries=1, backoff_factor_seconds=1.0),
        risk_level=RiskLevel.LOW,
        requires_approval=False,
        permission_scope="research:read",
        resource_limits=ResourceLimits(max_input_length=500, max_output_bytes=262_144),
        audit_policy=AuditPolicy(audit_event_type="COMPETITOR_DISCOVERY"),
    )

    def execute(
        self,
        input_data: DiscoverCompetitorsInput,
        context: dict[str, Any] | None = None,
    ) -> DiscoverCompetitorsOutput:
        """Execute competitor discovery using domain directory and query matching."""
        domain_key = input_data.domain.lower().strip()
        geo = input_data.geography or "Global"
        ctx = context or {}
        run_id = str(ctx.get("run_id", "run-discover"))
        step_id = str(ctx.get("step_identifier", "step-discover"))

        logger.info("discovering_competitors", domain=domain_key, geography=geo)

        # Match known domain entities or fall back to general software profiles
        entities = KNOWN_DOMAIN_ENTITIES.get(domain_key)
        if not entities:
            # Fuzzy match domain keywords
            for k, v in KNOWN_DOMAIN_ENTITIES.items():
                if k in domain_key or domain_key in k:
                    entities = v
                    break

        if not entities:
            # General fallback software profile
            entities = [
                {
                    "name": f"{input_data.domain.capitalize()} Leader Corp",
                    "domain": domain_key,
                    "description": f"Dominant market provider of {domain_key} enterprise solutions.",
                    "primary_url": f"https://example.com/{domain_key}/leader",
                    "market_tier": "tier-1",
                },
                {
                    "name": f"{input_data.domain.capitalize()} Disruptor AI",
                    "domain": domain_key,
                    "description": f"Challenger platform offering automated AI-driven {domain_key}.",
                    "primary_url": f"https://example.com/{domain_key}/disruptor",
                    "market_tier": "tier-2",
                },
            ]

        selected = entities[: input_data.max_results]
        competitors = [CompetitorEntity(**item) for item in selected]

        evidence_records: list[dict[str, Any]] = []
        for comp in competitors:
            ev = EvidenceService.create_evidence_record(
                run_id=run_id,
                step_identifier=step_id,
                tool_name=self.tool_id,
                source_url=comp.primary_url,
                snippet=f"Identified competitor '{comp.name}' in {comp.domain}: {comp.description}",
                metadata={"competitor_name": comp.name, "tier": comp.market_tier},
            )
            evidence_records.append(ev)

        return DiscoverCompetitorsOutput(
            domain=input_data.domain,
            geography=geo,
            competitors=competitors,
            total_found=len(competitors),
            evidence_records=evidence_records,
        )
