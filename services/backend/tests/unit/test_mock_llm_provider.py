"""Unit tests for MockLLMProvider deterministic generation and schema compliance."""

import pytest

from app.core.exceptions import DeterministicValidationError, TransientWorkerError
from app.providers.mock import MockLLMProvider
from app.schemas.llm import (
    AnalysisOutput,
    ExtractionOutput,
    PlanGenerationOutput,
    ReportDraftOutput,
)


@pytest.fixture
def mock_provider() -> MockLLMProvider:
    return MockLLMProvider(seed=42)


def test_mock_generate_plan_schema_valid(mock_provider: MockLLMProvider) -> None:
    """Verify plan generation returns schema-valid PlanGenerationOutput."""
    res = mock_provider.generate_plan(
        objective="Analyze AI code completion tools in North America",
        domain="developer-tools",
        geography="North America",
    )
    assert res.provider == "mock"
    assert res.model == "mock-analytical-v1"
    assert isinstance(res.data, PlanGenerationOutput)
    assert res.data.domain == "developer-tools"
    assert len(res.data.steps) == 3
    assert all(
        s.tool_name in {"web_search", "fetch_document", "extract_metrics"} for s in res.data.steps
    )
    assert res.usage.prompt_tokens > 0
    assert res.usage.completion_tokens > 0
    assert res.usage.cost_usd == 0


def test_mock_extract_information_schema_valid(mock_provider: MockLLMProvider) -> None:
    """Verify information extraction returns schema-valid ExtractionOutput."""
    sample_text = "CompetitorA offers a Cloud Platform starting at $49/mo. 99.95% uptime SLA."
    res = mock_provider.extract_information(sample_text)

    assert isinstance(res.data, ExtractionOutput)
    assert res.data.competitor_name == "CompetitorA"
    assert len(res.data.products) >= 1
    assert "49" in str(res.data.pricing_summary)
    assert len(res.data.key_assertions) >= 1


def test_mock_generate_analysis_schema_valid(mock_provider: MockLLMProvider) -> None:
    """Verify analysis generation returns schema-valid AnalysisOutput."""
    res = mock_provider.generate_analysis([{"competitor": "CompetitorA"}])

    assert isinstance(res.data, AnalysisOutput)
    assert len(res.data.competitor_comparisons) >= 2
    assert len(res.data.strategic_inferences) >= 1
    assert all(c.competitor_name for c in res.data.competitor_comparisons)


def test_mock_draft_report_separates_evidence_from_inference(
    mock_provider: MockLLMProvider,
) -> None:
    """Verify drafted report cleanly bifurcates empirical evidence from strategic inferences."""
    res = mock_provider.draft_report(
        objective="Compare enterprise AI observability platforms",
        analysis={"market": "observability"},
        evidence_records=[{"source_url": "https://example.com/spec", "hash": "abc"}],
    )

    assert isinstance(res.data, ReportDraftOutput)
    assert "Empirical Findings (Grounded Evidence)" in res.data.grounded_findings
    assert "Strategic Inferences & Analysis" in res.data.strategic_inferences
    assert "# Competitive Intelligence Report" in res.data.markdown_content


def test_mock_reproducibility_with_identical_seed() -> None:
    """Verify bit-for-bit determinism across two provider instances with identical seeds."""
    p1 = MockLLMProvider(seed=123)
    p2 = MockLLMProvider(seed=123)

    plan1 = p1.generate_plan("Test objective", domain="fintech")
    plan2 = p2.generate_plan("Test objective", domain="fintech")

    assert plan1.data.model_dump() == plan2.data.model_dump()
    assert plan1.usage.model_dump() == plan2.usage.model_dump()


def test_mock_simulation_failure_flags(mock_provider: MockLLMProvider) -> None:
    """Verify mock provider failure simulation triggers expected exception categories."""
    with pytest.raises(TransientWorkerError):
        mock_provider.generate_plan(
            "Test", domain="ai", constraints={"__test_fail_timeout__": True}
        )

    with pytest.raises(DeterministicValidationError):
        mock_provider.extract_information("Text", schema_hints={"__test_fail_malformed__": True})
