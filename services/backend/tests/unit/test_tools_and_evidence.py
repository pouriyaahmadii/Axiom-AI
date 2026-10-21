"""Unit tests for the AgentOps safe tool sandbox, SSRF guards, and evidence provenance layer."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.security import SecurityValidationError
from app.tools import (
    ALLOWED_TASK_TYPES,
    BaseTool,
    CitationAuditor,
    EvidenceService,
    ExtractMetricsTool,
    FetchDocumentTool,
    ToolMetadata,
    ToolRegistry,
    WebSearchTool,
    get_tool_registry,
)


@pytest.mark.unit
class TestToolRegistry:
    """Test tool registry allowlisting, bounds, and execution dispatch."""

    def test_registry_contains_approved_tools_only(self) -> None:
        registry = get_tool_registry()
        for tool_name in ALLOWED_TASK_TYPES:
            assert registry.is_allowed(tool_name)
            tool = registry.get_tool(tool_name)
            assert tool.tool_id == tool_name

    def test_unauthorized_tool_registration_rejected(self) -> None:
        class MaliciousTool(BaseTool):
            metadata = ToolMetadata(
                tool_id="execute_shell",
                name="Malicious Shell Tool",
                description="Run arbitrary bash scripts in environment",
                input_schema=WebSearchTool.metadata.input_schema,
                output_schema=WebSearchTool.metadata.output_schema,
            )

            def execute(self, _input_data: Any, _context: Any = None) -> Any:
                return WebSearchTool.metadata.output_schema(
                    query="ls", hits=[], total_hits=0, search_provider="none"
                )

        registry = ToolRegistry()
        with pytest.raises(SecurityValidationError) as exc:
            registry.register(MaliciousTool())

        assert "Security policy violation" in str(exc.value)
        assert "execute_shell" in str(exc.value)

    def test_executing_unauthorized_tool_returns_failure_result(self) -> None:
        registry = get_tool_registry()
        result = registry.execute("execute_arbitrary_code", {"cmd": "ls -la"})
        assert not result.success
        assert "Security violation" in (result.error or "")
        assert result.tool_id == "execute_arbitrary_code"


@pytest.mark.unit
class TestWebSearchTool:
    """Test guarded web search tool with corpus matching and input validation."""

    def test_empty_query_rejected(self) -> None:
        tool = WebSearchTool()
        result = tool.run(query="")
        assert not result.success
        assert "query" in (result.error or "").lower()

    def test_oversized_query_rejected(self) -> None:
        tool = WebSearchTool()
        result = tool.run(query="a" * 501)
        assert not result.success
        assert "500" in (result.error or "") or "query" in (result.error or "").lower()

    def test_successful_search_returns_hits_and_evidence(self) -> None:
        tool = WebSearchTool()
        result = tool.run(query="cloud monitoring", domain="observability", limit=3)
        assert result.success
        assert result.data["total_hits"] <= 3
        assert len(result.data["hits"]) > 0
        assert len(result.evidence_records) > 0

        first_hit = result.data["hits"][0]
        assert "url" in first_hit
        assert "snippet" in first_hit
        assert "content_hash" in first_hit

        # Check evidence record
        first_ev = result.evidence_records[0]
        assert first_ev["tool_name"] == "web_search"
        assert EvidenceService.verify_evidence_integrity(first_ev)


@pytest.mark.unit
class TestFetchDocumentTool:
    """Test SSRF protection, size caps, and hermetic document retrieval."""

    def test_empty_url_without_domain_rejected(self) -> None:
        tool = FetchDocumentTool()
        result = tool.run(url="")
        assert not result.success
        assert "url" in (result.error or "").lower()

    def test_ssrf_blocked_for_loopback(self) -> None:
        tool = FetchDocumentTool()
        result = tool.run(url="http://127.0.0.1:8000/admin")
        assert not result.success
        assert "SSRF" in (result.error or "")

    def test_ssrf_blocked_for_private_rfc1918_network(self) -> None:
        tool = FetchDocumentTool()
        result = tool.run(url="http://192.168.1.100/config")
        assert not result.success
        assert "SSRF" in (result.error or "")

    def test_ssrf_blocked_for_cloud_metadata(self) -> None:
        tool = FetchDocumentTool()
        result = tool.run(url="http://169.254.169.254/latest/meta-data/")
        assert not result.success
        assert "SSRF" in (result.error or "")

    def test_hermetic_offline_fetch_for_rfc2606_domain(self) -> None:
        tool = FetchDocumentTool()
        result = tool.run(url="https://example.com/datadog/pricing")
        assert result.success
        assert result.data["status_code"] == 200
        assert "Datadog" in result.data["content"]
        assert result.content_hash is not None
        assert len(result.evidence_records) == 1
        assert EvidenceService.verify_evidence_integrity(result.evidence_records[0])

    def test_html_tag_stripping(self) -> None:
        raw_html = (
            "<html><head><script>alert('bad');</script></head>"
            "<body><h1>Competitor Pricing</h1><p>Starting at $29/mo.</p></body></html>"
        )
        cleaned = FetchDocumentTool._strip_html(raw_html)
        assert "alert" not in cleaned
        assert "<script>" not in cleaned
        assert cleaned == "Competitor Pricing Starting at $29/mo."


@pytest.mark.unit
class TestExtractMetricsTool:
    """Test quantitative data parsing and verbatim grounding excerpts."""

    def test_extract_pricing_and_sla(self) -> None:
        tool = ExtractMetricsTool()
        sample_text = (
            "Enterprise platform offering standard tier at $49/mo per user. "
            "Guaranteed 99.95% uptime SLA with continuous multi-region failover."
        )
        result = tool.run(text=sample_text, domain="cloud")
        assert result.success
        metrics = result.data["metrics"]
        assert "$49/mo" in metrics.get("pricing", "")
        assert "99.95%" in metrics.get("sla_uptime", "")
        assert len(result.evidence_records) >= 2


@pytest.mark.unit
class TestEvidenceService:
    """Test text canonicalization, SHA-256 hashing, and tamper detection."""

    def test_text_normalization(self) -> None:
        raw = "  Line 1   \n\t  Line   2  \n "
        assert EvidenceService.normalize_text(raw) == "Line 1 Line 2"

    def test_hash_determinism(self) -> None:
        text1 = "Enterprise observability starting at $15/host/mo."
        text2 = "  Enterprise   observability starting at   $15/host/mo. \n"
        assert EvidenceService.compute_content_hash(text1) == EvidenceService.compute_content_hash(
            text2
        )

    def test_tamper_detection(self) -> None:
        record = EvidenceService.create_evidence_record(
            run_id="run-1",
            step_identifier="step-1",
            tool_name="web_search",
            source_url="https://example.com",
            snippet="Original uncorrupted factual assertion.",
        )
        assert EvidenceService.verify_evidence_integrity(record)

        # Alter snippet content
        corrupted_record = dict(record)
        corrupted_record["snippet"] = "Tampered false claim injected after hash creation."
        assert not EvidenceService.verify_evidence_integrity(corrupted_record)


@pytest.mark.unit
class TestCitationAuditor:
    """Test citation extraction, grounding verification, and hallucination detection."""

    def test_extract_citation_markers(self) -> None:
        text = (
            "# Market Report\n"
            "Datadog prices infrastructure at $15/mo [E1]. "
            "New Relic offers 100 GB ingest free [E2]. "
            "Dynatrace guarantees 99.99% SLA [ev-abc12345]."
        )
        markers = CitationAuditor.extract_citations_from_markdown(text)
        assert markers == ["E1", "E2", "ev-abc12345"]

    def test_clean_citation_audit_passes(self) -> None:
        ev1 = EvidenceService.create_evidence_record(
            run_id="run-1",
            step_identifier="step-1",
            tool_name="fetch_document",
            source_url="https://example.com/p1",
            snippet="Datadog prices infrastructure at $15/mo.",
        )
        ev2 = EvidenceService.create_evidence_record(
            run_id="run-1",
            step_identifier="step-2",
            tool_name="fetch_document",
            source_url="https://example.com/p2",
            snippet="New Relic offers 100 GB ingest free.",
        )

        report = {
            "markdown_content": "Finding 1: Datadog pricing is $15/mo [E1]. Finding 2: Free ingest [E2].",
            "citations": [{"evidence_id": ev1["evidence_id"]}, {"evidence_id": ev2["evidence_id"]}],
        }

        result = CitationAuditor.audit_report_grounding(report, [ev1, ev2])
        assert result.is_grounded
        assert result.total_citations_found == 2
        assert len(result.hallucinated_citations) == 0
        assert result.coverage_score == 1.0

    def test_hallucinated_citation_detected(self) -> None:
        ev1 = EvidenceService.create_evidence_record(
            run_id="run-1",
            step_identifier="step-1",
            tool_name="web_search",
            source_url="https://example.com/real",
            snippet="Real empirical evidence.",
        )

        report = {
            "markdown_content": (
                "Real claim backed by data [E1]. Fabricated assertion with phantom citation [E99]."
            ),
            "citations": [],
        }

        result = CitationAuditor.audit_report_grounding(report, [ev1])
        assert not result.is_grounded
        assert "E99" in result.hallucinated_citations
        assert result.verified_citations_count == 1
