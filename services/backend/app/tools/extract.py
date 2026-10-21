"""Tool: extract_structured_facts - Extracts verifiable facts, metrics, and verbatim snippets."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.logging import get_logger
from app.providers import get_llm_provider
from app.tools.base import BaseTool
from app.tools.evidence import EvidenceService
from app.tools.models import (
    AuditPolicy,
    ResourceLimits,
    RetryPolicy,
    RiskLevel,
    ToolMetadata,
)

logger = get_logger("agentops.tools.extract")

PRICE_PATTERN = re.compile(
    r"(\$\d+(?:\.\d+)?(?:\s*/\s*(?:mo|month|user|host|hour))?)", re.IGNORECASE
)
PERCENTAGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?%)")
SLA_PATTERN = re.compile(r"(\b99(?:\.\d+)?%(?:\s*(?:SLA|uptime|availability))?)", re.IGNORECASE)


class ExtractFactsInput(BaseModel):
    """Input payload for structured fact and metric extraction."""

    model_config = ConfigDict(extra="ignore")

    text: str = Field(default="", max_length=50_000, description="Source document text to analyze")
    domain: str | None = Field(
        default=None, description="Domain context for domain-specific extractions"
    )
    source_url: str | None = Field(default=None, description="Provenance source URL for grounding")
    categories: list[str] = Field(
        default_factory=lambda: ["pricing", "sla", "features", "compliance"],
        description="Target factual categories to extract",
    )


class ExtractedFactItem(BaseModel):
    """Single empirical fact anchored to a verbatim source excerpt."""

    category: str
    fact: str
    verbatim_snippet: str
    confidence: float = 1.0
    snippet_hash: str


class ExtractFactsOutput(BaseModel):
    """Normalized structured facts and metrics output schema."""

    domain: str
    facts: list[ExtractedFactItem]
    metrics: dict[str, Any]
    total_facts: int
    cost_usd: float = 0.0
    evidence_records: list[dict[str, Any]] = Field(default_factory=list)


class ExtractStructuredFactsTool(BaseTool[ExtractFactsInput, ExtractFactsOutput]):
    """Allowlisted tool extracting structured commercial facts and verbatim grounding snippets."""

    metadata = ToolMetadata(
        tool_id="extract_structured_facts",
        name="Extract Structured Facts",
        description="Extract quantitative facts, commercial pricing, availability SLAs, and verbatim grounding excerpts.",
        input_schema=ExtractFactsInput,
        output_schema=ExtractFactsOutput,
        timeout_seconds=20.0,
        retry_policy=RetryPolicy(max_retries=1, backoff_factor_seconds=1.0),
        risk_level=RiskLevel.LOW,
        requires_approval=False,
        permission_scope="research:read",
        resource_limits=ResourceLimits(max_input_length=50_000, max_output_bytes=262_144),
        audit_policy=AuditPolicy(audit_event_type="FACT_EXTRACTION"),
    )

    def execute(
        self,
        input_data: ExtractFactsInput,
        context: dict[str, Any] | None = None,
    ) -> ExtractFactsOutput:
        """Extract structured facts using deterministic regex and LLM semantic parsing."""
        text = input_data.text.strip()
        domain = input_data.domain or "general"
        source_url = input_data.source_url or "https://example.com/source"
        ctx = context or {}
        run_id = str(ctx.get("run_id", "run-extract"))
        step_id = str(ctx.get("step_identifier", "step-extract"))
        provider_name = ctx.get("llm_provider")

        logger.info("extracting_structured_facts", domain=domain, text_len=len(text))

        facts: list[ExtractedFactItem] = []
        metrics: dict[str, Any] = {}
        evidence_records: list[dict[str, Any]] = []

        # 1. Deterministic Extraction for High-Assurance Grounding
        prices = PRICE_PATTERN.findall(text)
        slas = SLA_PATTERN.findall(text)
        percentages = [p for p in PERCENTAGE_PATTERN.findall(text) if p not in slas]

        if prices:
            metrics["pricing"] = prices[0]
            match = re.search(re.escape(prices[0]), text)
            if match:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                snippet = text[start:end].strip()
                s_hash = EvidenceService.compute_content_hash(snippet)
                facts.append(
                    ExtractedFactItem(
                        category="pricing",
                        fact=f"Base pricing is {prices[0]}",
                        verbatim_snippet=snippet,
                        snippet_hash=s_hash,
                    )
                )
                evidence_records.append(
                    EvidenceService.create_evidence_record(
                        run_id=run_id,
                        step_identifier=step_id,
                        tool_name=self.tool_id,
                        source_url=source_url,
                        snippet=snippet,
                        metadata={"metric_type": "pricing", "value": prices[0]},
                    )
                )

        if slas:
            metrics["sla_uptime"] = slas[0]
            match = re.search(re.escape(slas[0]), text)
            if match:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                snippet = text[start:end].strip()
                s_hash = EvidenceService.compute_content_hash(snippet)
                facts.append(
                    ExtractedFactItem(
                        category="sla",
                        fact=f"Availability commitment is {slas[0]}",
                        verbatim_snippet=snippet,
                        snippet_hash=s_hash,
                    )
                )
                evidence_records.append(
                    EvidenceService.create_evidence_record(
                        run_id=run_id,
                        step_identifier=step_id,
                        tool_name=self.tool_id,
                        source_url=source_url,
                        snippet=snippet,
                        metadata={"metric_type": "sla", "value": slas[0]},
                    )
                )

        if percentages:
            metrics["percentages"] = percentages

        # 2. LLM Extraction Boundary
        llm_cost_usd = 0.0
        try:
            llm = get_llm_provider(provider_name)
            llm_result = llm.extract_information(text)
            extracted_data = llm_result.data.model_dump()
            metrics["llm_extraction"] = extracted_data
            llm_cost_usd = float(llm_result.usage.cost_usd)

            for prod in extracted_data.get("products", []):
                snippet = prod.get("description", "")[:200]
                s_hash = EvidenceService.compute_content_hash(snippet)
                facts.append(
                    ExtractedFactItem(
                        category=prod.get("category") or "features",
                        fact=f"{prod.get('name')}: {prod.get('description')}",
                        verbatim_snippet=snippet,
                        snippet_hash=s_hash,
                    )
                )
        except Exception as exc:
            logger.warning("llm_extraction_unavailable", reason=str(exc))

        return ExtractFactsOutput(
            domain=domain,
            facts=facts,
            metrics=metrics,
            total_facts=len(facts),
            cost_usd=llm_cost_usd,
            evidence_records=evidence_records,
        )


# Backward-compatible alias for existing agent runtime
class ExtractMetricsTool(ExtractStructuredFactsTool):
    """Backward-compatible alias for 'extract_metrics'."""

    metadata = ToolMetadata(
        tool_id="extract_metrics",
        name="Extract Metrics",
        description="Extract quantitative facts and verbatim grounding snippets (legacy alias).",
        input_schema=ExtractFactsInput,
        output_schema=ExtractFactsOutput,
        timeout_seconds=20.0,
        retry_policy=RetryPolicy(max_retries=1, backoff_factor_seconds=1.0),
        risk_level=RiskLevel.LOW,
        requires_approval=False,
        permission_scope="research:read",
        resource_limits=ResourceLimits(max_input_length=50_000, max_output_bytes=262_144),
        audit_policy=AuditPolicy(audit_event_type="FACT_EXTRACTION"),
    )
