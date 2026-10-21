"""Tool: generate_report_draft - Synthesizes comprehensive research reports with grounding citations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.providers import get_llm_provider
from app.tools.base import BaseTool
from app.tools.citation_auditor import CitationAuditor
from app.tools.models import (
    AuditPolicy,
    ResourceLimits,
    RetryPolicy,
    RiskLevel,
    ToolMetadata,
)

logger = get_logger("agentops.tools.report")


class GenerateReportDraftInput(BaseModel):
    """Input payload for report draft synthesis."""

    objective: str = Field(min_length=5, max_length=2000, description="Analytical objective")
    domain: str = Field(min_length=2, max_length=100, description="Industry sector")
    evidence_records: list[dict[str, Any]] = Field(
        default_factory=list, description="Pool of captured empirical evidence records"
    )
    comparison_summary: str | None = Field(
        default=None, description="Optional entity comparison findings summary"
    )
    llm_provider: str | None = Field(default=None, description="Active LLM provider adapter")


class GenerateReportDraftOutput(BaseModel):
    """Synthesized research report deliverable schema."""

    title: str
    executive_summary: str
    grounded_findings: str
    strategic_inferences: str
    markdown_content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    grounding_coverage_score: float = 1.0
    evidence_records: list[dict[str, Any]] = Field(default_factory=list)


class GenerateReportDraftTool(BaseTool[GenerateReportDraftInput, GenerateReportDraftOutput]):
    """Allowlisted tool synthesizing research reports with explicit grounding citations."""

    metadata = ToolMetadata(
        tool_id="generate_report_draft",
        name="Generate Report Draft",
        description="Synthesize structured analytical reports strictly grounded in captured empirical evidence records.",
        input_schema=GenerateReportDraftInput,
        output_schema=GenerateReportDraftOutput,
        timeout_seconds=30.0,
        retry_policy=RetryPolicy(max_retries=1, backoff_factor_seconds=1.0),
        risk_level=RiskLevel.HIGH,
        requires_approval=False,
        permission_scope="research:synthesize",
        resource_limits=ResourceLimits(max_input_length=50_000, max_output_bytes=524_288),
        audit_policy=AuditPolicy(audit_event_type="REPORT_SYNTHESIS"),
    )

    def execute(
        self,
        input_data: GenerateReportDraftInput,
        context: dict[str, Any] | None = None,
    ) -> GenerateReportDraftOutput:
        """Synthesize report draft using LLM provider and audit grounding."""
        ctx = context or {}
        provider_name = input_data.llm_provider or ctx.get("llm_provider")
        evidence = input_data.evidence_records or ctx.get("evidence_items", [])

        logger.info(
            "generating_report_draft",
            objective=input_data.objective[:50],
            domain=input_data.domain,
            evidence_count=len(evidence),
        )

        llm = get_llm_provider(provider_name)
        analysis_payload = {
            "domain": input_data.domain,
            "comparison": input_data.comparison_summary,
            "evidence_count": len(evidence),
        }

        # Synthesize report via LLM provider
        draft_res = llm.draft_report(
            objective=input_data.objective,
            analysis=analysis_payload,
            evidence_records=evidence,
        )
        report_data = draft_res.data.model_dump()

        # Audit citation grounding
        audit_res = CitationAuditor.audit_report_grounding(report_data, evidence)

        return GenerateReportDraftOutput(
            title=report_data["title"],
            executive_summary=report_data["executive_summary"],
            grounded_findings=report_data["grounded_findings"],
            strategic_inferences=report_data["strategic_inferences"],
            markdown_content=report_data["markdown_content"],
            citations=report_data.get("citations", []),
            grounding_coverage_score=audit_res.coverage_score,
            evidence_records=evidence,
        )
