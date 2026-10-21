"""Unit tests for Phase 14: Traceable Evidence Management and Grounded Report Generation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.evidence.models import (
    ClaimType,
    CompetitorComparisonItem,
    ConfidenceLevel,
    ReportClaim,
    ReportEvaluationMetadata,
    RetrievalStatus,
    SourceRecord,
    ValidatedReport,
    ValidationStatus,
)
from app.evidence.pipeline import EvidencePipeline
from app.evidence.service import EvidencePersistenceService


@pytest.mark.unit
class TestEvidencePipelineSources:
    """Test source registration, URL canonicalization, and staleness detection."""

    def test_source_registration_and_url_normalization(self) -> None:
        pipeline = EvidencePipeline()
        raw_url = "HTTPS://WWW.DatadogHQ.COM/pricing/?utm_source=google&ref=campaign#tier1"
        source = pipeline.register_source(
            url=raw_url,
            title="Datadog Official Pricing",
            content="Infrastructure monitoring starts at $15 per host per month.",
        )

        assert source.source_id.startswith("src-")
        assert source.url == "https://www.datadoghq.com/pricing/"
        assert source.publisher_or_host == "datadoghq.com"
        assert source.title == "Datadog Official Pricing"
        assert source.retrieval_status == RetrievalStatus.SUCCESS
        assert len(source.content_hash) == 64

        # Deduplication check: registering the exact same canonical URL returns existing record
        dup_source = pipeline.register_source(url=raw_url)
        assert dup_source.source_id == source.source_id

    def test_source_staleness_tracking(self) -> None:
        pipeline = EvidencePipeline(max_age_days=90)
        old_time = datetime.now(timezone.utc) - timedelta(days=120)

        source = pipeline.register_source(
            url="https://example.com/legacy-pricing",
            retrieved_at=old_time,
            content="Historical 2024 pricing",
        )

        assert source.retrieval_status == RetrievalStatus.STALE

        # Registering evidence under a stale source should cascade to STALE validation status
        ev = pipeline.register_evidence(
            source_id=source.source_id,
            extracted_passage="Historical pricing is $10/mo",
            related_entity="LegacyComp",
            related_claim="Entry pricing",
        )
        assert ev.validation_status == ValidationStatus.STALE

    def test_empty_url_rejected(self) -> None:
        pipeline = EvidencePipeline()
        with pytest.raises(ValueError, match="URL cannot be empty"):
            pipeline.register_source(url="   ")


@pytest.mark.unit
class TestEvidencePipelineEvidence:
    """Test empirical evidence excerpt registration, hashing, and integrity checks."""

    def test_invalid_source_id_rejected(self) -> None:
        pipeline = EvidencePipeline()
        with pytest.raises(ValueError, match="Invalid source ID 'src-nonexistent'"):
            pipeline.register_evidence(
                source_id="src-nonexistent",
                extracted_passage="Valid passage text",
                related_entity="Competitor A",
                related_claim="Pricing",
            )

    def test_evidence_registration_and_integrity_verification(self) -> None:
        pipeline = EvidencePipeline()
        src = pipeline.register_source(
            url="https://dynatrace.com/pricing",
            publisher_or_host="dynatrace.com",
            content="Dynatrace Full Stack Monitoring starts at $0.08 per hour per 8GB host.",
        )

        passage = "  Dynatrace Full Stack   Monitoring starts at $0.08 per hour per 8GB host.  "
        ev = pipeline.register_evidence(
            source_id=src.source_id,
            extracted_passage=passage,
            related_entity="Dynatrace",
            related_claim="Full stack pricing is $0.08/hr/8GB host",
        )

        assert ev.evidence_id.startswith("ev-")
        assert ev.source_id == src.source_id
        assert (
            ev.extracted_passage
            == "Dynatrace Full Stack Monitoring starts at $0.08 per hour per 8GB host."
        )
        assert ev.validation_status == ValidationStatus.VALID
        assert pipeline.verify_evidence_integrity(ev.evidence_id)

    def test_empty_passage_or_entity_rejected(self) -> None:
        pipeline = EvidencePipeline()
        src = pipeline.register_source(url="https://example.com")

        with pytest.raises(ValueError, match="Extracted evidence passage cannot be empty"):
            pipeline.register_evidence(
                source_id=src.source_id,
                extracted_passage="",
                related_entity="Entity",
                related_claim="Claim",
            )

        with pytest.raises(ValueError, match="Related entity cannot be empty"):
            pipeline.register_evidence(
                source_id=src.source_id,
                extracted_passage="Valid snippet",
                related_entity=" ",
                related_claim="Claim",
            )


@pytest.mark.unit
class TestEpistemicClaimsAndGrounding:
    """Test claim typing, missing evidence detection, and unknown value protection."""

    def test_direct_fact_requires_valid_evidence(self) -> None:
        pipeline = EvidencePipeline()
        src = pipeline.register_source(
            url="https://datadog.com", content="APM starts at $31 per host/month"
        )
        ev = pipeline.register_evidence(
            source_id=src.source_id,
            extracted_passage="APM starts at $31 per host/month",
            related_entity="Datadog",
            related_claim="APM pricing",
        )

        # 1. Supported direct fact
        valid_fact = ReportClaim(
            claim_id="claim-1",
            claim_type=ClaimType.DIRECT_FACT,
            entity="Datadog",
            statement="Datadog APM starts at $31/host/month.",
            evidence_ids=[ev.evidence_id],
        )
        audited_valid = pipeline.audit_claim(valid_fact)
        assert audited_valid.is_supported is True

        # 2. Unsupported direct fact (missing evidence IDs)
        unsupported_fact_no_ids = ReportClaim(
            claim_id="claim-2",
            claim_type=ClaimType.DIRECT_FACT,
            entity="Datadog",
            statement="Datadog log ingestion is $0.10/GB.",
            evidence_ids=[],
        )
        audited_no_ids = pipeline.audit_claim(unsupported_fact_no_ids)
        assert audited_no_ids.is_supported is False

        # 3. Unsupported direct fact (referencing non-existent evidence ID)
        unsupported_fact_bad_id = ReportClaim(
            claim_id="claim-3",
            claim_type=ClaimType.DIRECT_FACT,
            entity="Datadog",
            statement="Datadog synthesizes tests at $5 per 1k runs.",
            evidence_ids=["ev-fabricated123"],
        )
        audited_bad_id = pipeline.audit_claim(unsupported_fact_bad_id)
        assert audited_bad_id.is_supported is False

    def test_unknown_value_protection(self) -> None:
        """A report must never silently convert an unknown value into a factual claim."""
        pipeline = EvidencePipeline()

        unknown_claim = ReportClaim(
            claim_id="claim-unknown",
            claim_type=ClaimType.UNKNOWN,
            entity="Splunk",
            statement="Enterprise volume pricing is undisclosed on public web pages and requires sales inquiry.",
            evidence_ids=[],
            confidence=ConfidenceLevel.HEURISTIC,
        )

        audited = pipeline.audit_claim(unknown_claim)
        assert audited.claim_type == ClaimType.UNKNOWN
        assert audited.is_supported is True

    def test_report_epistemic_audit_metrics(self) -> None:
        pipeline = EvidencePipeline()
        src = pipeline.register_source(url="https://datadog.com", content="Valid source content")
        ev = pipeline.register_evidence(
            source_id=src.source_id,
            extracted_passage="Valid excerpt",
            related_entity="Datadog",
            related_claim="Valid claim",
        )

        claims = [
            ReportClaim(
                claim_id="c1",
                claim_type=ClaimType.DIRECT_FACT,
                entity="Datadog",
                statement="Supported fact statement.",
                evidence_ids=[ev.evidence_id],
            ),
            ReportClaim(
                claim_id="c2",
                claim_type=ClaimType.DIRECT_FACT,
                entity="Datadog",
                statement="Unsupported fact statement.",
                evidence_ids=[],
            ),
            ReportClaim(
                claim_id="c3",
                claim_type=ClaimType.INFERENCE,
                entity="Datadog",
                statement="Datadog positions as an all-in-one suite.",
                evidence_ids=[ev.evidence_id],
            ),
            ReportClaim(
                claim_id="c4",
                claim_type=ClaimType.RECOMMENDATION,
                entity="Self",
                statement="Adopt open telemetry ingestion to counter vendor lock-in.",
                evidence_ids=[],
            ),
            ReportClaim(
                claim_id="c5",
                claim_type=ClaimType.UNKNOWN,
                entity="New Relic",
                statement="Private cloud SLA terms are undisclosed.",
                evidence_ids=[],
            ),
        ]

        audited_claims, meta = pipeline.audit_report(
            claims=claims,
            executive_summary="Summary of findings across competitors.",
            positioning_analysis="Detailed positioning analysis.",
        )

        assert meta.total_claims == 5
        assert meta.direct_facts_count == 2
        assert meta.inferences_count == 1
        assert meta.recommendations_count == 1
        assert meta.unknowns_count == 1
        assert meta.unsupported_claims == ["c2"]
        assert meta.is_valid is False
        assert meta.grounding_coverage_score == 0.5  # 1 supported out of 2 direct facts


@pytest.mark.unit
class TestContradictionPreservation:
    """Test conflicting evidence preservation without arbitrary bias."""

    def test_preserve_conflicting_prices(self) -> None:
        pipeline = EvidencePipeline()
        src1 = pipeline.register_source(
            url="https://site1.com/pricing", content="Datadog Pro tier starts at $15 per host."
        )
        src2 = pipeline.register_source(
            url="https://site2.com/review",
            content="Datadog entry plan starts at $29 billed annually.",
        )

        ev1 = pipeline.register_evidence(
            source_id=src1.source_id,
            extracted_passage="Datadog Pro tier starts at $15 per host.",
            related_entity="Datadog",
            related_claim="Pricing",
        )
        ev2 = pipeline.register_evidence(
            source_id=src2.source_id,
            extracted_passage="Datadog entry plan starts at $29 billed annually.",
            related_entity="Datadog",
            related_claim="Pricing",
        )

        contra = pipeline.add_contradiction(
            dimension="Base Pricing",
            entity="Datadog",
            conflicting_passages=[
                {
                    "evidence_id": ev1.evidence_id,
                    "source_id": src1.source_id,
                    "passage": ev1.extracted_passage,
                },
                {
                    "evidence_id": ev2.evidence_id,
                    "source_id": src2.source_id,
                    "passage": ev2.extracted_passage,
                },
            ],
            resolution_note="Source 1 cites monthly infrastructure baseline; Source 2 reflects enterprise bundle tier.",
        )

        assert contra.dimension == "Base Pricing"
        assert contra.entity == "Datadog"
        assert len(contra.conflicting_passages) == 2
        assert "monthly infrastructure baseline" in contra.resolution_note
        assert len(pipeline.list_contradictions()) == 1


@pytest.mark.unit
class TestReproducibilityAndRendering:
    """Test bit-for-bit reproducibility digest and markdown rendering."""

    def test_reproducibility_hash_determinism(self) -> None:
        def build_pipe() -> tuple[EvidencePipeline, list[ReportClaim]]:
            p = EvidencePipeline()
            s = p.register_source(url="https://datadog.com", content="Pricing passage")
            e = p.register_evidence(
                source_id=s.source_id,
                extracted_passage="Pricing passage",
                related_entity="Datadog",
                related_claim="Pricing",
            )
            c = [
                ReportClaim(
                    claim_id="c1",
                    claim_type=ClaimType.DIRECT_FACT,
                    entity="Datadog",
                    statement="Starts at $15.",
                    evidence_ids=[e.evidence_id],
                )
            ]
            return p, c

        p1, c1 = build_pipe()
        _, m1 = p1.audit_report(c1, "Exec summary", "Positioning")

        p2, c2 = build_pipe()
        _, m2 = p2.audit_report(c2, "Exec summary", "Positioning")

        assert m1.reproducibility_hash == m2.reproducibility_hash

    def test_report_renderer_formatting(self) -> None:
        pipeline = EvidencePipeline()
        src = pipeline.register_source(
            url="https://datadog.com/pricing",
            title="Datadog Pricing",
            publisher_or_host="datadoghq.com",
            content="Datadog APM starts at $31/host/mo.",
        )
        ev = pipeline.register_evidence(
            source_id=src.source_id,
            extracted_passage="Datadog APM starts at $31/host/mo.",
            related_entity="Datadog",
            related_claim="APM pricing",
        )

        comparison = [
            CompetitorComparisonItem(
                competitor_name="Datadog",
                pricing_summary="From $15/host/mo",
                sla_availability="99.9% Uptime",
                key_features=["APM", "Logs", "Synthetics"],
                deployment_models=["SaaS", "Agent"],
                limitations=["High egress cost"],
            )
        ]

        claims = [
            ReportClaim(
                claim_id="c1",
                claim_type=ClaimType.DIRECT_FACT,
                entity="Datadog",
                statement="Datadog APM starts at $31/host/mo.",
                evidence_ids=[ev.evidence_id],
            ),
            ReportClaim(
                claim_id="c2",
                claim_type=ClaimType.UNKNOWN,
                entity="Datadog",
                statement="Volume discount tiers are unlisted.",
                evidence_ids=[],
            ),
        ]

        report = pipeline.build_validated_report(
            title="Observability Competitor Benchmark 2026",
            domain="DevOps & Observability",
            executive_summary="Comprehensive competitor analysis for cloud observability.",
            claims=claims,
            positioning_analysis="Datadog commands premier enterprise mindshare.",
            competitor_comparison=comparison,
            limitations=["Data gathered exclusively from public pricing pages."],
        )

        md = report.markdown_content
        assert "# Observability Competitor Benchmark 2026" in md
        assert "## 1. Executive Summary" in md
        assert "## 2. Competitor Comparison Matrix" in md
        assert "| **Datadog** |" in md
        assert "## 3. Evidence-Linked Findings" in md
        assert "`[DIRECT FACT]`" in md
        assert "[E1]" in md
        assert "## 6. Limitations, Unknowns & Freshness Boundaries" in md
        assert "Data Gap" in md
        assert "## 7. Sources & Provenance Bibliography" in md
        assert "datadoghq.com" in md
        assert "## 8. Provenance & Reproducibility Audit" in md
        assert report.evaluation_metadata.reproducibility_hash in md

    def test_unsupported_claim_flagged_in_markdown(self) -> None:
        pipeline = EvidencePipeline()
        src = pipeline.register_source(url="https://example.com", content="Example content")
        pipeline.register_evidence(
            source_id=src.source_id,
            extracted_passage="Example content",
            related_entity="Ex",
            related_claim="Ex",
        )

        claims = [
            ReportClaim(
                claim_id="c-unsupported",
                claim_type=ClaimType.DIRECT_FACT,
                entity="Competitor X",
                statement="Claims 99.999% SLA without evidence.",
                evidence_ids=[],  # missing
            )
        ]

        report = pipeline.build_validated_report(
            title="SLA Benchmark Report",
            domain="Cloud",
            executive_summary="Testing unsupported claim flagging in report renderer.",
            claims=claims,
            positioning_analysis="Testing analysis section.",
        )

        assert "⚠️ **[UNSUPPORTED CLAIM: Missing Verified Evidence]**" in report.markdown_content
        assert report.evaluation_metadata.is_valid is False
        assert "c-unsupported" in report.evaluation_metadata.unsupported_claims


@pytest.mark.unit
class TestReportSchemaValidation:
    """Test schema constraints on ValidatedReport and components."""

    def test_short_title_or_summary_rejected(self) -> None:
        meta = ReportEvaluationMetadata(
            total_claims=1,
            direct_facts_count=0,
            inferences_count=1,
            recommendations_count=0,
            unknowns_count=0,
            supported_claims_count=1,
            unsupported_claims=[],
            contradictions_count=0,
            grounding_coverage_score=1.0,
            is_valid=True,
            reproducibility_hash="a" * 64,
        )

        src = SourceRecord(
            source_id="src-1",
            url="https://example.com",
            publisher_or_host="example.com",
            content_hash="h" * 64,
        )

        claim = ReportClaim(
            claim_id="c1",
            claim_type=ClaimType.INFERENCE,
            entity="Test",
            statement="An analytical statement with sufficient length.",
        )

        with pytest.raises(ValidationError):
            ValidatedReport(
                title="Tiny",  # min_length is 5
                domain="tech",
                executive_summary="Too short",  # min_length is 20
                evidence_linked_findings=[claim],
                positioning_analysis="Sufficiently long positioning analysis.",
                sources=[src],
                evaluation_metadata=meta,
                markdown_content="Adequately long markdown content text here for testing.",
            )


@pytest.mark.unit
@pytest.mark.asyncio
class TestEvidencePersistenceService:
    """Test database persistence mapping for sources, evidence, and reports."""

    async def test_persist_pipeline_bundle_with_mock_session(self) -> None:
        pipeline = EvidencePipeline()
        src = pipeline.register_source(url="https://datadog.com", content="Pricing is $15/host/mo")
        ev = pipeline.register_evidence(
            source_id=src.source_id,
            extracted_passage="Pricing is $15/host/mo",
            related_entity="Datadog",
            related_claim="Pricing",
        )

        claims = [
            ReportClaim(
                claim_id="c1",
                claim_type=ClaimType.DIRECT_FACT,
                entity="Datadog",
                statement="Pricing is $15/host/mo.",
                evidence_ids=[ev.evidence_id],
            )
        ]

        report = pipeline.build_validated_report(
            title="Datadog Pricing Analysis",
            domain="Observability",
            executive_summary="Summary of Datadog pricing models and plans.",
            claims=claims,
            positioning_analysis="Datadog positioning analysis.",
        )

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        run_id = uuid.uuid4()
        (
            sources,
            evidence,
            persisted_report,
        ) = await EvidencePersistenceService.persist_pipeline_bundle(
            session=mock_session,
            run_id=run_id,
            pipeline=pipeline,
            report=report,
        )

        assert len(sources) == 1
        assert len(evidence) == 1
        assert persisted_report is not None
        assert persisted_report.title == "Datadog Pricing Analysis"
        assert mock_session.add.call_count >= 3
