"""Traceable evidence pipeline managing intelligence ingestion, hashing, staleness, contradictions, and report grounding."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urlunparse

from app.core.logging import get_logger
from app.evidence.models import (
    ClaimType,
    CompetitorComparisonItem,
    ContradictionRecord,
    EvidenceRecord,
    ExtractionStatus,
    ReportClaim,
    ReportEvaluationMetadata,
    RetrievalStatus,
    SourceRecord,
    SourceType,
    ValidatedReport,
    ValidationStatus,
)

logger = get_logger("agentops.evidence.pipeline")


class EvidencePipeline:
    """Manages the lifecycle, cryptographic integrity, staleness, and claim grounding of intelligence data."""

    def __init__(self, max_age_days: int = 90) -> None:
        self.max_age_days = max_age_days
        self._sources: dict[str, SourceRecord] = {}
        self._url_to_source_id: dict[str, str] = {}
        self._evidence: dict[str, EvidenceRecord] = {}
        self._contradictions: list[ContradictionRecord] = []

    # ------------------------------------------------------------------
    # Normalization & Hashing
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_url(url: str) -> str:
        """Produce canonical normalized URL (lowercased host, stripped tracking params and fragments)."""
        if not url or not url.strip():
            return ""
        parsed = urlparse(url.strip())
        netloc = (parsed.netloc or "").lower()
        if not netloc:
            return ""
        # Drop standard tracking query parameters
        query_parts = [
            q
            for q in parsed.query.split("&")
            if q and not any(q.lower().startswith(prefix) for prefix in ("utm_", "ref=", "fbclid="))
        ]
        clean_query = "&".join(query_parts)
        # Drop fragment
        return urlunparse(
            (parsed.scheme.lower() or "https", netloc, parsed.path or "/", "", clean_query, "")
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        """Collapse redundant whitespace and strip leading/trailing whitespace."""
        if not text:
            return ""
        return re.sub(r"\s+", " ", str(text)).strip()

    @classmethod
    def compute_sha256(cls, text: str) -> str:
        """Deterministic SHA-256 hash of normalized text."""
        canonical = cls.normalize_text(text)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def extract_publisher_or_host(cls, url: str) -> str:
        """Extract domain hostname or fallback publisher name from URL."""
        if not url:
            return "unknown-publisher"
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path.split("/")[0]
        # Remove common 'www.' prefix
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown-publisher"

    # ------------------------------------------------------------------
    # Source Ingestion & Staleness Tracking
    # ------------------------------------------------------------------

    def register_source(
        self,
        url: str,
        title: str | None = None,
        publisher_or_host: str | None = None,
        source_type: SourceType = SourceType.WEB_PAGE,
        retrieved_at: datetime | None = None,
        retrieval_status: RetrievalStatus = RetrievalStatus.SUCCESS,
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SourceRecord:
        """Register external intelligence source with SHA-256 hashing and staleness verification."""
        if not url or not url.strip():
            raise ValueError("URL cannot be empty when registering a source.")
        canonical_url = self.normalize_url(url)
        if not canonical_url:
            raise ValueError(f"Invalid or unparseable URL '{url}' when registering a source.")

        # Check existing registration for this normalized URL
        if canonical_url in self._url_to_source_id:
            return self._sources[self._url_to_source_id[canonical_url]]

        retrieval_time = retrieved_at or datetime.now(timezone.utc)
        if retrieval_time.tzinfo is None:
            retrieval_time = retrieval_time.replace(tzinfo=timezone.utc)

        # Content hash
        content_hash = self.compute_sha256(content or canonical_url)
        source_id = f"src-{content_hash[:8]}"

        # Derive host if not provided
        derived_publisher = publisher_or_host or self.extract_publisher_or_host(canonical_url)

        # Staleness evaluation
        now = datetime.now(timezone.utc)
        age_in_days = (now - retrieval_time).total_seconds() / (24 * 3600)
        final_status = retrieval_status
        if age_in_days > self.max_age_days and retrieval_status == RetrievalStatus.SUCCESS:
            final_status = RetrievalStatus.STALE

        record = SourceRecord(
            source_id=source_id,
            url=canonical_url,
            title=self.normalize_text(title) if title else None,
            publisher_or_host=derived_publisher,
            retrieved_at=retrieval_time,
            content_hash=content_hash,
            source_type=source_type,
            retrieval_status=final_status,
            metadata=dict(metadata or {}),
        )

        self._sources[source_id] = record
        self._url_to_source_id[canonical_url] = source_id

        logger.debug(
            "source_registered",
            source_id=source_id,
            url=canonical_url,
            publisher=derived_publisher,
            status=final_status.value,
        )
        return record

    def get_source(self, source_id: str) -> SourceRecord | None:
        """Retrieve source record by ID."""
        return self._sources.get(source_id)

    def list_sources(self) -> list[SourceRecord]:
        """Return all registered source records."""
        return list(self._sources.values())

    # ------------------------------------------------------------------
    # Evidence Ingestion & Cryptographic Integrity
    # ------------------------------------------------------------------

    def register_evidence(
        self,
        source_id: str,
        extracted_passage: str,
        related_entity: str,
        related_claim: str,
        retrieved_at: datetime | None = None,
        extraction_status: ExtractionStatus = ExtractionStatus.EXTRACTED,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceRecord:
        """Register verifiable empirical evidence excerpt linked to a registered source."""
        # Validate source ID existence
        source = self.get_source(source_id)
        if not source:
            raise ValueError(
                f"Invalid source ID '{source_id}': source must be registered before evidence."
            )

        clean_passage = self.normalize_text(extracted_passage)
        if not clean_passage:
            raise ValueError("Extracted evidence passage cannot be empty.")

        clean_entity = self.normalize_text(related_entity)
        if not clean_entity:
            raise ValueError("Related entity cannot be empty.")

        clean_claim = self.normalize_text(related_claim)
        if not clean_claim:
            raise ValueError("Related claim cannot be empty.")

        content_hash = self.compute_sha256(clean_passage)
        evidence_id = f"ev-{content_hash[:12]}"

        # Determine validation status (check staleness of source)
        extraction_time = retrieved_at or datetime.now(timezone.utc)
        if extraction_time.tzinfo is None:
            extraction_time = extraction_time.replace(tzinfo=timezone.utc)

        validation_status = ValidationStatus.VALID
        if source.retrieval_status == RetrievalStatus.STALE:
            validation_status = ValidationStatus.STALE

        record = EvidenceRecord(
            evidence_id=evidence_id,
            source_id=source_id,
            extracted_passage=clean_passage,
            related_entity=clean_entity,
            related_claim=clean_claim,
            retrieved_at=extraction_time,
            extraction_status=extraction_status,
            validation_status=validation_status,
            content_hash=content_hash,
            metadata=dict(metadata or {}),
        )

        self._evidence[evidence_id] = record

        logger.debug(
            "evidence_registered",
            evidence_id=evidence_id,
            source_id=source_id,
            entity=clean_entity,
            validation_status=validation_status.value,
        )
        return record

    def get_evidence(self, evidence_id: str) -> EvidenceRecord | None:
        """Retrieve evidence record by ID."""
        return self._evidence.get(evidence_id)

    def list_evidence(self) -> list[EvidenceRecord]:
        """Return all registered evidence records."""
        return list(self._evidence.values())

    def verify_evidence_integrity(self, evidence_id: str) -> bool:
        """Verify that an evidence record's passage exactly matches its recorded SHA-256 hash."""
        ev = self.get_evidence(evidence_id)
        if not ev:
            return False
        expected_hash = self.compute_sha256(ev.extracted_passage)
        return bool(expected_hash == ev.content_hash)

    # ------------------------------------------------------------------
    # Contradiction Management (Preserve Rather Than Discard)
    # ------------------------------------------------------------------

    def add_contradiction(
        self,
        dimension: str,
        entity: str,
        conflicting_passages: list[dict[str, Any]],
        resolution_note: str,
    ) -> ContradictionRecord:
        """Record conflicting market evidence transparently without biased arbitrary resolution.

        Requirements:
        - Preserve contradictions rather than arbitrarily choosing a preferred value.
        - Document both conflicting passages and provide neutral context.
        """
        clean_dim = self.normalize_text(dimension)
        clean_ent = self.normalize_text(entity)
        clean_note = self.normalize_text(resolution_note)

        if not conflicting_passages or len(conflicting_passages) < 2:
            raise ValueError("Contradictions require at least two conflicting evidence points.")

        record = ContradictionRecord(
            dimension=clean_dim,
            entity=clean_ent,
            conflicting_passages=conflicting_passages,
            resolution_note=clean_note,
        )
        self._contradictions.append(record)

        logger.info(
            "contradiction_preserved",
            dimension=clean_dim,
            entity=clean_ent,
            conflicting_count=len(conflicting_passages),
        )
        return record

    def list_contradictions(self) -> list[ContradictionRecord]:
        """Return all preserved contradiction records."""
        return list(self._contradictions)

    # ------------------------------------------------------------------
    # Claim Grounding & Audit
    # ------------------------------------------------------------------

    def audit_claim(self, claim: ReportClaim) -> ReportClaim:
        """Audit individual claim according to epistemic classification and evidence linkage.

        Epistemic Rules:
        - DIRECT_FACT: Must reference at least one existing, untampered evidence ID.
        - INFERENCE: Analytical hypothesis, may reference evidence or synthesize findings.
        - RECOMMENDATION: Prescriptive operational guidance.
        - UNKNOWN: Explicitly unknown or unavailable data; must NOT masquerade as fact.
        """
        claim_type = claim.claim_type
        evidence_ids = claim.evidence_ids or []
        is_supported = True
        contradiction_notes = claim.contradiction_notes

        if claim_type == ClaimType.DIRECT_FACT:
            if not evidence_ids:
                is_supported = False
            else:
                for eid in evidence_ids:
                    ev = self.get_evidence(eid)
                    if not ev:
                        is_supported = False
                        break
                    # Verify cryptographic integrity
                    if not self.verify_evidence_integrity(eid):
                        is_supported = False
                        break

        elif claim_type == ClaimType.UNKNOWN:
            # An unknown value must explicitly remain unknown and not claim factual certainty
            is_supported = True

        return ReportClaim(
            claim_id=claim.claim_id,
            claim_type=claim.claim_type,
            entity=claim.entity,
            statement=claim.statement,
            evidence_ids=evidence_ids,
            confidence=claim.confidence,
            is_supported=is_supported,
            contradiction_notes=contradiction_notes,
        )

    def audit_report(
        self,
        claims: list[ReportClaim],
        executive_summary: str,
        positioning_analysis: str = "",
    ) -> tuple[list[ReportClaim], ReportEvaluationMetadata]:
        """Perform comprehensive epistemic audit on all report claims and calculate grounding metrics."""
        audited_claims: list[ReportClaim] = []
        unsupported_claim_ids: list[str] = []

        direct_facts_count = 0
        inferences_count = 0
        recommendations_count = 0
        unknowns_count = 0
        supported_claims_count = 0

        for raw_claim in claims:
            audited = self.audit_claim(raw_claim)
            audited_claims.append(audited)

            if audited.claim_type == ClaimType.DIRECT_FACT:
                direct_facts_count += 1
                if audited.is_supported:
                    supported_claims_count += 1
                else:
                    unsupported_claim_ids.append(audited.claim_id)

            elif audited.claim_type == ClaimType.INFERENCE:
                inferences_count += 1
                if audited.is_supported:
                    supported_claims_count += 1

            elif audited.claim_type == ClaimType.RECOMMENDATION:
                recommendations_count += 1
                if audited.is_supported:
                    supported_claims_count += 1

            elif audited.claim_type == ClaimType.UNKNOWN:
                unknowns_count += 1
                supported_claims_count += 1

        total_claims = len(claims)
        # Grounding coverage: ratio of supported direct facts to total direct facts
        if direct_facts_count > 0:
            coverage_score = round(
                (direct_facts_count - len(unsupported_claim_ids)) / direct_facts_count, 3
            )
        else:
            coverage_score = 1.0

        is_valid = len(unsupported_claim_ids) == 0

        # Compute deterministic reproducibility hash
        reproducibility_hash = self.compute_reproducibility_hash(
            audited_claims=audited_claims,
            executive_summary=executive_summary,
            positioning_analysis=positioning_analysis,
        )

        metadata = ReportEvaluationMetadata(
            total_claims=total_claims,
            direct_facts_count=direct_facts_count,
            inferences_count=inferences_count,
            recommendations_count=recommendations_count,
            unknowns_count=unknowns_count,
            supported_claims_count=supported_claims_count,
            unsupported_claims=unsupported_claim_ids,
            contradictions_count=len(self._contradictions),
            grounding_coverage_score=coverage_score,
            is_valid=is_valid,
            reproducibility_hash=reproducibility_hash,
        )

        logger.info(
            "report_audit_completed",
            total_claims=total_claims,
            direct_facts=direct_facts_count,
            unsupported=len(unsupported_claim_ids),
            coverage=coverage_score,
            is_valid=is_valid,
        )
        return audited_claims, metadata

    def compute_reproducibility_hash(
        self,
        audited_claims: list[ReportClaim],
        executive_summary: str,
        positioning_analysis: str,
    ) -> str:
        """Calculate bit-for-bit reproducible SHA-256 digest of evidence pool and claims."""
        hasher = hashlib.sha256()

        # Incorporate all evidence passages in sorted order
        sorted_ev = sorted(self._evidence.values(), key=lambda e: e.evidence_id)
        for ev in sorted_ev:
            hasher.update(ev.evidence_id.encode("utf-8"))
            hasher.update(ev.content_hash.encode("utf-8"))

        # Incorporate all audited claims
        sorted_claims = sorted(audited_claims, key=lambda c: c.claim_id)
        for c in sorted_claims:
            hasher.update(c.claim_id.encode("utf-8"))
            hasher.update(c.claim_type.value.encode("utf-8"))
            hasher.update(c.statement.encode("utf-8"))
            for eid in sorted(c.evidence_ids):
                hasher.update(eid.encode("utf-8"))

        # Incorporate contradictions
        for contra in sorted(self._contradictions, key=lambda ct: (ct.dimension, ct.entity)):
            hasher.update(contra.dimension.encode("utf-8"))
            hasher.update(contra.entity.encode("utf-8"))
            hasher.update(contra.resolution_note.encode("utf-8"))

        # Incorporate narrative anchors
        hasher.update(self.normalize_text(executive_summary).encode("utf-8"))
        hasher.update(self.normalize_text(positioning_analysis).encode("utf-8"))

        return hasher.hexdigest()

    # ------------------------------------------------------------------
    # Validated Report Synthesis
    # ------------------------------------------------------------------

    def build_validated_report(
        self,
        title: str,
        domain: str,
        executive_summary: str,
        claims: list[ReportClaim],
        positioning_analysis: str,
        competitor_comparison: list[CompetitorComparisonItem] | None = None,
        limitations: list[str] | None = None,
        renderer: Any | None = None,
    ) -> ValidatedReport:
        """Assemble and validate a full ValidatedReport instance conforming to Phase 14 specifications."""
        audited_claims, evaluation_meta = self.audit_report(
            claims=claims,
            executive_summary=executive_summary,
            positioning_analysis=positioning_analysis,
        )

        sources = self.list_sources()
        if not sources:
            raise ValueError(
                "Cannot build validated report without at least one registered source."
            )

        retrieval_timestamps = {s.source_id: s.retrieved_at.isoformat() for s in sources}

        # Render markdown content
        from app.evidence.renderer import ReportRenderer

        active_renderer = renderer or ReportRenderer()
        markdown_content = active_renderer.render(
            title=title,
            domain=domain,
            executive_summary=executive_summary,
            competitor_comparison=competitor_comparison or [],
            findings=audited_claims,
            positioning_analysis=positioning_analysis,
            limitations=limitations or [],
            contradictions=self.list_contradictions(),
            sources=sources,
            evidence=self.list_evidence(),
            evaluation_metadata=evaluation_meta,
        )

        return ValidatedReport(
            title=title,
            domain=domain,
            executive_summary=executive_summary,
            competitor_comparison=competitor_comparison or [],
            evidence_linked_findings=audited_claims,
            positioning_analysis=positioning_analysis,
            limitations=limitations or [],
            contradictions=self.list_contradictions(),
            sources=sources,
            retrieval_timestamps=retrieval_timestamps,
            evaluation_metadata=evaluation_meta,
            markdown_content=markdown_content,
        )
