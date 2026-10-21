"""Deterministic Mock LLM Provider for hermetic testing, CI, and local zero-cost evaluation."""

from __future__ import annotations

import random
from decimal import Decimal
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from app.core.exceptions import DeterministicValidationError, TransientWorkerError
from app.providers.base import BaseLLMProvider, validate_structured_output
from app.schemas.llm import (
    AnalysisOutput,
    CompetitorComparison,
    ExtractionOutput,
    LLMResponse,
    LLMUsageMetrics,
    PlanGenerationOutput,
    PlanStepDefinition,
    ProductFeature,
    ReportDraftOutput,
)

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock provider producing reproducible, schema-validated outputs."""

    def __init__(self, seed: int = 42, model_name: str = "mock-analytical-v1") -> None:
        self._seed = seed
        self._model_name = model_name
        self._rng = random.Random(seed)

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _make_metrics(
        self, prompt_tokens: int = 150, completion_tokens: int = 250
    ) -> LLMUsageMetrics:
        """Create deterministic simulated usage metrics."""
        return LLMUsageMetrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=Decimal("0.000000"),
            latency_ms=12.5,
        )

    def generate_plan(
        self,
        objective: str,
        domain: str,
        geography: str | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> LLMResponse[PlanGenerationOutput]:
        """Synthesize a deterministic 3-step competitive intelligence plan."""
        # Optional test simulation injection
        if constraints and constraints.get("__test_fail_timeout__"):
            raise TransientWorkerError("Mock provider simulated timeout during plan generation.")

        steps = [
            PlanStepDefinition(
                step_index=1,
                step_identifier="search_market_landscape",
                title=f"Search public landscape for {domain} in {geography or 'global'}",
                tool_name="web_search",
                parameters={
                    "query": f"{domain} competitors market comparison {geography or ''}".strip()
                },
                requires_human_approval=False,
            ),
            PlanStepDefinition(
                step_index=2,
                step_identifier="fetch_competitor_documentation",
                title="Fetch documentation and pricing sheets for leading players",
                tool_name="fetch_document",
                parameters={"domain": domain, "depth": 2},
                requires_human_approval=False,
            ),
            PlanStepDefinition(
                step_index=3,
                step_identifier="extract_competitive_metrics",
                title="Extract structured feature matrix and commercial metrics",
                tool_name="extract_metrics",
                parameters={"domain": domain},
                requires_human_approval=False,
            ),
        ]

        data = PlanGenerationOutput(
            objective=objective,
            domain=domain,
            steps=steps,
            estimated_complexity="medium",
            rationale=f"Bounded 3-step investigation targeting {domain} public disclosures and pricing models.",
        )

        return LLMResponse(
            data=data,
            provider=self.provider_name,
            model=self.model_name,
            usage=self._make_metrics(prompt_tokens=120, completion_tokens=180),
            raw_content=data.model_dump_json(indent=2),
        )

    def extract_information(
        self,
        document_text: str,
        schema_hints: dict[str, Any] | None = None,
    ) -> LLMResponse[ExtractionOutput]:
        """Extract deterministic competitor product, pricing, and claims from text."""
        if schema_hints and schema_hints.get("__test_fail_malformed__"):
            raise DeterministicValidationError("Simulated malformed extraction.")

        # Derive entity name deterministically or fallback to standard demo entity
        competitor_name = "Acme Intelligence Corp"
        if "CompetitorA" in document_text:
            competitor_name = "CompetitorA"
        elif "CompetitorB" in document_text:
            competitor_name = "CompetitorB"

        data = ExtractionOutput(
            competitor_name=competitor_name,
            products=[
                ProductFeature(
                    name="Core Analytics Platform",
                    description="Cloud-native operations tracking and model metrics observability.",
                    category="Platform",
                ),
                ProductFeature(
                    name="API Gateway Integration",
                    description="High-throughput ingress routing with strict token budgeting.",
                    category="Infrastructure",
                ),
            ],
            pricing_summary="Tiered subscription: Free community tier, $49/mo Developer, Custom Enterprise SLAs.",
            target_customers=["Enterprise IT", "Engineering Leads", "AI Platform Architects"],
            key_assertions=[
                "Guarantees 99.95% API uptime on enterprise tier.",
                "Supports self-hosted deployment via Docker Compose and Kubernetes.",
                "Zero third-party model data retention on dedicated clusters.",
            ],
        )

        return LLMResponse(
            data=data,
            provider=self.provider_name,
            model=self.model_name,
            usage=self._make_metrics(prompt_tokens=210, completion_tokens=220),
            raw_content=data.model_dump_json(indent=2),
        )

    def generate_analysis(
        self,
        extracted_data: list[dict[str, Any]],
        focus_areas: list[str] | None = None,
    ) -> LLMResponse[AnalysisOutput]:
        """Generate comparative analysis matrix from extracted facts."""
        _ = (extracted_data, focus_areas)
        comparisons = [
            CompetitorComparison(
                competitor_name="Acme Intelligence Corp",
                strengths=[
                    "Self-hosted privacy-first architecture",
                    "Comprehensive outbox transaction durability",
                    "Zero paid API key requirement in local mode",
                ],
                weaknesses=[
                    "Requires local Docker or container runtime",
                    "Bounded plan step ceiling limits open-ended scraping",
                ],
                market_position="Leader in self-hosted autonomous agent operations.",
            ),
            CompetitorComparison(
                competitor_name="CloudAgent SaaS",
                strengths=[
                    "Turnkey hosted cloud infrastructure",
                    "Pre-integrated enterprise SSO and team billing",
                ],
                weaknesses=[
                    "High per-run token markups",
                    "Black-box execution without step-by-step reproducible audit trails",
                ],
                market_position="Challenger targeting small non-technical marketing teams.",
            ),
        ]

        data = AnalysisOutput(
            industry="AI Systems and Autonomous Agent Operations",
            market_overview=(
                "The competitive landscape is bifurcated between hosted SaaS solutions offering speed but opaque "
                "observability, and self-hosted open architectures delivering complete data sovereignty and auditability."
            ),
            competitor_comparisons=comparisons,
            strategic_inferences=[
                "Self-hosted platforms will gain share among regulated industries requiring strict data governance.",
                "Deterministic mock capabilities will become standard evaluation criteria for enterprise procurement.",
            ],
        )

        return LLMResponse(
            data=data,
            provider=self.provider_name,
            model=self.model_name,
            usage=self._make_metrics(prompt_tokens=320, completion_tokens=340),
            raw_content=data.model_dump_json(indent=2),
        )

    def draft_report(
        self,
        objective: str,
        analysis: dict[str, Any],
        evidence_records: list[dict[str, Any]],
    ) -> LLMResponse[ReportDraftOutput]:
        """Draft a structured markdown report clearly separating evidence from inferences."""
        _ = analysis
        executive_summary = (
            f"This competitive intelligence investigation evaluated the market landscape for objective: '{objective}'. "
            "Findings confirm substantial divergence in privacy guarantees, commercial pricing, and self-hosted support."
        )

        grounded_findings = (
            "## Empirical Findings (Grounded Evidence)\n\n"
            "- **Acme Intelligence Corp** provides full self-hosted Docker deployment with zero data retention.\n"
            "- Commercial pricing features a verified tiered model starting from free community edition to $49/mo.\n"
            f"- Analysis grounded against {len(evidence_records) or 2} verifiable source records."
        )

        strategic_inferences = (
            "## Strategic Inferences & Analysis\n\n"
            "- Self-hosted agent infrastructure reduces compliance overhead by up to 60% for enterprise teams.\n"
            "- Platforms supporting deterministic mock testing demonstrate faster CI deployment cycles."
        )

        markdown_content = (
            f"# Competitive Intelligence Report\n\n"
            f"**Objective**: {objective}\n\n"
            f"## Executive Summary\n\n{executive_summary}\n\n"
            f"{grounded_findings}\n\n"
            f"{strategic_inferences}\n\n"
            f"## Provenance & Methodology\n\n"
            "All empirical statements are cited and verified against cryptographic evidence records."
        )

        data = ReportDraftOutput(
            title=f"Competitive Analysis: {objective[:60]}",
            executive_summary=executive_summary,
            grounded_findings=grounded_findings,
            strategic_inferences=strategic_inferences,
            markdown_content=markdown_content,
        )

        return LLMResponse(
            data=data,
            provider=self.provider_name,
            model=self.model_name,
            usage=self._make_metrics(prompt_tokens=450, completion_tokens=500),
            raw_content=data.model_dump_json(indent=2),
        )

    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> LLMResponse[T]:
        """Generic structured generation adhering to the target Pydantic response model."""
        _ = system_prompt
        # For known models, route to dedicated generator
        if issubclass(response_model, PlanGenerationOutput):
            res = self.generate_plan(prompt, domain="technology")
            return LLMResponse(
                data=cast(T, res.data),
                provider=self.provider_name,
                model=self.model_name,
                usage=res.usage,
                raw_content=res.raw_content,
            )
        if issubclass(response_model, ExtractionOutput):
            ext_res = self.extract_information(prompt)
            return LLMResponse(
                data=cast(T, ext_res.data),
                provider=self.provider_name,
                model=self.model_name,
                usage=ext_res.usage,
                raw_content=ext_res.raw_content,
            )

        # Fallback: instantiate response_model with default dummy fields
        try:
            # Attempt to construct default instance or validate empty dict
            data = validate_structured_output({}, response_model)
        except Exception:
            # If default instantiation fails, create minimal dict
            schema_fields = response_model.model_fields
            dummy: dict[str, Any] = {}
            for field_name, field_info in schema_fields.items():
                if field_info.annotation is str:
                    dummy[field_name] = f"Mock {field_name}"
                elif field_info.annotation is int:
                    dummy[field_name] = 1
                elif field_info.annotation is bool:
                    dummy[field_name] = False
                elif (
                    field_info.annotation is list
                    or getattr(field_info.annotation, "__origin__", None) is list
                ):
                    dummy[field_name] = []
                elif (
                    field_info.annotation is dict
                    or getattr(field_info.annotation, "__origin__", None) is dict
                ):
                    dummy[field_name] = {}
                else:
                    dummy[field_name] = None
            data = validate_structured_output(dummy, response_model)

        return LLMResponse(
            data=data,
            provider=self.provider_name,
            model=self.model_name,
            usage=self._make_metrics(prompt_tokens=100, completion_tokens=100),
            raw_content=None,
        )
