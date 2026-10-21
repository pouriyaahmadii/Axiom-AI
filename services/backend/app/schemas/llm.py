"""Structured schemas for LLM provider outputs, token usage, and capability contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class LLMUsageMetrics(BaseModel):
    """Token usage, cost modeling, and latency tracking for a model call."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = Field(default=0, ge=0, description="Number of tokens in prompt")
    completion_tokens: int = Field(
        default=0, ge=0, description="Number of tokens generated in completion"
    )
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    cost_usd: Decimal = Field(
        default=Decimal("0.000000"), ge=Decimal("0"), description="Estimated cost in USD"
    )
    latency_ms: float = Field(default=0.0, ge=0.0, description="Execution duration in milliseconds")


class LLMResponse(BaseModel, Generic[T]):
    """Standardized response envelope returned by all LLM provider adapters."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: T = Field(description="Structured validated output data")
    provider: str = Field(description="Name of provider adapter, e.g. 'mock', 'openai', 'ollama'")
    model: str = Field(description="Model identifier, e.g. 'mock-v1', 'gpt-4o-mini', 'llama3.2'")
    usage: LLMUsageMetrics = Field(
        default_factory=LLMUsageMetrics, description="Usage and latency metrics"
    )
    raw_content: str | None = Field(
        default=None, description="Optional raw textual output before parsing"
    )


# 1. Capability: Structured Plan Generation


class PlanStepDefinition(BaseModel):
    """A discrete task step inside an LLM-synthesized execution plan."""

    step_index: int = Field(ge=1, description="Sequential 1-based index of the step")
    step_identifier: str = Field(min_length=2, max_length=64, description="Unique slug for step")
    title: str = Field(min_length=3, max_length=200, description="Descriptive human-readable title")
    tool_name: str = Field(
        min_length=2, max_length=64, description="Allowlisted tool name to invoke"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Typed parameters for the tool"
    )
    requires_human_approval: bool = Field(
        default=False, description="Whether this step requires human oversight"
    )


class PlanGenerationOutput(BaseModel):
    """Structured execution plan synthesized by an LLM."""

    objective: str = Field(min_length=5, description="Echoed analytical objective")
    domain: str = Field(min_length=2, description="Target domain classification")
    steps: list[PlanStepDefinition] = Field(
        min_length=1, max_length=20, description="Sequential steps"
    )
    estimated_complexity: str = Field(
        default="medium", description="Complexity rating: low, medium, or high"
    )
    rationale: str | None = Field(default=None, description="Reasoning behind step composition")


# 2. Capability: Structured Information Extraction


class ProductFeature(BaseModel):
    """Extracted feature or offering from competitor documentation."""

    name: str = Field(min_length=1, description="Feature or capability name")
    description: str = Field(description="Brief functional description")
    category: str | None = Field(default=None, description="Feature grouping or category")


class ExtractionOutput(BaseModel):
    """Structured entity, pricing, and feature extraction from unstructured source text."""

    competitor_name: str = Field(min_length=1, description="Name of competitor or product entity")
    products: list[ProductFeature] = Field(
        default_factory=list, description="Extracted products and features"
    )
    pricing_summary: str | None = Field(
        default=None, description="Summary of pricing tiers or model"
    )
    target_customers: list[str] = Field(
        default_factory=list, description="Identified audience or market segments"
    )
    key_assertions: list[str] = Field(
        default_factory=list, description="Factual claims extracted directly from source text"
    )


# 3. Capability: Analysis Generation


class CompetitorComparison(BaseModel):
    """Comparative profile between competitors."""

    competitor_name: str = Field(min_length=1, description="Name of competitor")
    strengths: list[str] = Field(default_factory=list, description="Key competitive strengths")
    weaknesses: list[str] = Field(
        default_factory=list, description="Identified limitations or drawbacks"
    )
    market_position: str = Field(description="Market positioning summary")


class AnalysisOutput(BaseModel):
    """Comparative strategic synthesis generated from extracted evidence."""

    industry: str = Field(description="Industry or market sector")
    market_overview: str = Field(description="High-level assessment of the competitive landscape")
    competitor_comparisons: list[CompetitorComparison] = Field(
        min_length=1, description="Detailed competitor comparison matrix"
    )
    strategic_inferences: list[str] = Field(
        default_factory=list, description="Inferences and hypotheses derived from evidence"
    )


# 4. Capability: Report Drafting


class ReportDraftOutput(BaseModel):
    """Final analytical report draft separating grounded facts from strategic inferences."""

    title: str = Field(min_length=5, max_length=200, description="Report headline")
    executive_summary: str = Field(min_length=20, description="Executive briefing")
    grounded_findings: str = Field(
        min_length=20, description="Empirical evidence section citing factual claims"
    )
    strategic_inferences: str = Field(
        min_length=20, description="Strategic interpretation clearly separated from evidence"
    )
    markdown_content: str = Field(
        min_length=50, description="Complete rendered markdown deliverable with section headings"
    )
