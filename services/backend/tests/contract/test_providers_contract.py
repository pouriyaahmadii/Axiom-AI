"""Contract tests verifying interchangeable provider substitution (Acceptance Criteria)."""

import json
from unittest.mock import MagicMock

import httpx
import pytest

from app.providers.base import BaseLLMProvider
from app.providers.mock import MockLLMProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider
from app.schemas.llm import (
    AnalysisOutput,
    ExtractionOutput,
    PlanGenerationOutput,
    ReportDraftOutput,
)

pytestmark = pytest.mark.contract


def _mock_openai_client() -> httpx.Client:
    mock_client = MagicMock(spec=httpx.Client)

    def _mock_post(_url: str, **kwargs: dict) -> httpx.Response:
        messages = kwargs.get("json", {}).get("messages", [])  # type: ignore[union-attr]
        sys_content = messages[0]["content"] if messages else ""

        if "PlanGenerationOutput" in sys_content:
            data = {
                "objective": "Contract objective",
                "domain": "software",
                "steps": [
                    {
                        "step_index": 1,
                        "step_identifier": "s1",
                        "title": "Search",
                        "tool_name": "web_search",
                        "parameters": {},
                        "requires_human_approval": False,
                    }
                ],
                "estimated_complexity": "low",
            }
        elif "ExtractionOutput" in sys_content:
            data = {
                "competitor_name": "ContractCorp",
                "products": [],
                "target_customers": ["Developers"],
                "key_assertions": ["Factual assertion"],
            }
        elif "AnalysisOutput" in sys_content:
            data = {
                "industry": "Software",
                "market_overview": "Overview",
                "competitor_comparisons": [
                    {
                        "competitor_name": "C1",
                        "strengths": [],
                        "weaknesses": [],
                        "market_position": "P1",
                    }
                ],
            }
        else:
            data = {
                "title": "Report Title",
                "executive_summary": "Summary with sufficient characters for validation",
                "grounded_findings": "Grounded findings with sufficient characters",
                "strategic_inferences": "Inferences with sufficient length to pass",
                "markdown_content": "# Markdown Content\n\nFull deliverable with sufficient length to pass the 50 char requirement.",
            }

        body = {
            "choices": [{"message": {"content": json.dumps(data)}}],
            "usage": {"prompt_tokens": 150, "completion_tokens": 200, "total_tokens": 350},
        }
        return httpx.Response(
            status_code=200,
            content=json.dumps(body).encode("utf-8"),
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )

    mock_client.post.side_effect = _mock_post
    return mock_client


def _mock_ollama_client() -> httpx.Client:
    mock_client = MagicMock(spec=httpx.Client)

    def _mock_post(_url: str, **kwargs: dict) -> httpx.Response:
        messages = kwargs.get("json", {}).get("messages", [])  # type: ignore[union-attr]
        sys_content = messages[0]["content"] if messages else ""

        if "PlanGenerationOutput" in sys_content:
            data = {
                "objective": "Contract objective",
                "domain": "software",
                "steps": [
                    {
                        "step_index": 1,
                        "step_identifier": "s1",
                        "title": "Search",
                        "tool_name": "web_search",
                        "parameters": {},
                        "requires_human_approval": False,
                    }
                ],
                "estimated_complexity": "low",
            }
        elif "ExtractionOutput" in sys_content:
            data = {
                "competitor_name": "ContractCorp",
                "products": [],
                "target_customers": ["Developers"],
                "key_assertions": ["Factual assertion"],
            }
        elif "AnalysisOutput" in sys_content:
            data = {
                "industry": "Software",
                "market_overview": "Overview",
                "competitor_comparisons": [
                    {
                        "competitor_name": "C1",
                        "strengths": [],
                        "weaknesses": [],
                        "market_position": "P1",
                    }
                ],
            }
        else:
            data = {
                "title": "Report Title",
                "executive_summary": "Summary with sufficient characters for validation",
                "grounded_findings": "Grounded findings with sufficient characters",
                "strategic_inferences": "Inferences with sufficient length to pass",
                "markdown_content": "# Markdown Content\n\nFull deliverable with sufficient length to pass the 50 char requirement.",
            }

        body = {
            "model": "llama3.2",
            "message": {"content": json.dumps(data)},
            "done": True,
            "total_duration": 300000000,
            "prompt_eval_count": 100,
            "eval_count": 150,
        }
        return httpx.Response(
            status_code=200,
            content=json.dumps(body).encode("utf-8"),
            request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
        )

    mock_client.post.side_effect = _mock_post
    return mock_client


@pytest.fixture(params=["mock", "openai", "ollama"])
def provider_instance(request: pytest.FixtureRequest) -> BaseLLMProvider:
    """Parametrized fixture providing each LLM adapter implementation."""
    provider_type = request.param
    if provider_type == "mock":
        return MockLLMProvider(seed=42)
    if provider_type == "openai":
        return OpenAIProvider(api_key="sk-test", http_client=_mock_openai_client())
    if provider_type == "ollama":
        return OllamaProvider(http_client=_mock_ollama_client())
    raise ValueError(f"Unknown provider: {provider_type}")


def test_provider_contract_substitutability(provider_instance: BaseLLMProvider) -> None:
    """Acceptance Criteria: Same high-level workflow executes identically across all providers."""
    # 1. Plan Generation
    plan_res = provider_instance.generate_plan(
        objective="Analyze AI code completion tools in North America",
        domain="developer-tools",
    )
    assert isinstance(plan_res.data, PlanGenerationOutput)
    assert len(plan_res.data.steps) >= 1
    assert plan_res.usage.total_tokens >= 0

    # 2. Information Extraction
    extract_res = provider_instance.extract_information("Competitor doc with facts.")
    assert isinstance(extract_res.data, ExtractionOutput)
    assert extract_res.data.competitor_name

    # 3. Analysis Generation
    analysis_res = provider_instance.generate_analysis([{"doc": "content"}])
    assert isinstance(analysis_res.data, AnalysisOutput)
    assert len(analysis_res.data.competitor_comparisons) >= 1

    # 4. Report Drafting
    report_res = provider_instance.draft_report(
        objective="Analyze AI tools",
        analysis=analysis_res.data.model_dump(),
        evidence_records=[],
    )
    assert isinstance(report_res.data, ReportDraftOutput)
    assert len(report_res.data.markdown_content) >= 50
