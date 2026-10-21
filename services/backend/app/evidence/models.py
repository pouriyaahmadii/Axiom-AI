"""Domain models, enums, and schemas for the traceable evidence and report generation pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    """Classification of external intelligence sources."""

    WEB_PAGE = "web_page"
    DOCUMENTATION = "documentation"
    PRICING_SHEET = "pricing_sheet"
    CORPUS = "corpus"
    API_RESPONSE = "api_response"


class RetrievalStatus(str, Enum):
    """Operational status of source ingestion."""

    SUCCESS = "success"
    FAILED = "failed"
    CACHED = "cached"
    TIMEOUT = "timeout"
    STALE = "stale"


class ExtractionStatus(str, Enum):
    """Status of evidence extraction from source material."""

    EXTRACTED = "extracted"
    TRUNCATED = "truncated"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class ValidationStatus(str, Enum):
    """Cryptographic and semantic integrity status of evidence."""

    VALID = "valid"
    HASH_MISMATCH = "hash_mismatch"
    CONTRADICTORY = "contradictory"
    STALE = "stale"
    UNVERIFIED = "unverified"


class ClaimType(str, Enum):
    """Classification of claims in the synthesized research report."""

    DIRECT_FACT = "direct_fact"  # Direct empirical statement grounded in verified evidence
    INFERENCE = "inference"  # Analytical hypothesis or deductive interpretation
    RECOMMENDATION = "recommendation"  # Prescriptive operational guidance
    UNKNOWN = "unknown"  # Explicitly unknown, unavailable, or non-disclosed data


class ConfidenceLevel(str, Enum):
    """Qualitative, uncalibrated heuristic confidence rating.

    Guarantees:
    - Never treated as a calibrated mathematical Bayesian probability.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    HEURISTIC = "heuristic"


class SourceRecord(BaseModel):
    """Canonical representation of an external intelligence source."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(description="Unique source identifier (e.g., src-87834e3a)")
    url: str = Field(description="Canonical normalized URL")
    title: str | None = Field(default=None, description="Document or page title")
    publisher_or_host: str = Field(description="Domain name, host, or publisher organization")
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC retrieval timestamp",
    )
    content_hash: str = Field(description="Cryptographic SHA-256 hash of retrieved content")
    source_type: SourceType = Field(default=SourceType.WEB_PAGE, description="Type of source")
    retrieval_status: RetrievalStatus = Field(
        default=RetrievalStatus.SUCCESS, description="Retrieval outcome status"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional source telemetry"
    )


class EvidenceRecord(BaseModel):
    """Verifiable empirical excerpt anchored to a specific source record."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str = Field(description="Unique evidence identifier (e.g., ev-87834e3a4bbe)")
    source_id: str = Field(description="Identifier of the source record this evidence derives from")
    extracted_passage: str = Field(
        description="Verbatim passage or concise empirical evidence excerpt"
    )
    related_entity: str = Field(description="Competitor or product entity this evidence concerns")
    related_claim: str = Field(
        description="Specific claim or data point this passage substantiates"
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC evidence extraction timestamp",
    )
    extraction_status: ExtractionStatus = Field(
        default=ExtractionStatus.EXTRACTED, description="Status of extraction"
    )
    validation_status: ValidationStatus = Field(
        default=ValidationStatus.VALID, description="Integrity validation status"
    )
    content_hash: str = Field(description="Cryptographic SHA-256 hash of the extracted passage")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Contextual metadata")


class ReportClaim(BaseModel):
    """Distinct report claim with strict evidence linkage and epistemic typing."""

    claim_id: str = Field(description="Stable claim identifier (e.g., claim-1)")
    claim_type: ClaimType = Field(
        description="Epistemic category: direct fact, inference, recommendation, or unknown"
    )
    entity: str = Field(description="Associated competitor or market subject")
    statement: str = Field(description="The textual claim statement")
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Referenced evidence IDs. Must be non-empty for DIRECT_FACT.",
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.HIGH,
        description="Qualitative uncalibrated confidence rating",
    )
    is_supported: bool = Field(
        default=True,
        description="Whether this claim has verified, untampered supporting evidence",
    )
    contradiction_notes: str | None = Field(
        default=None,
        description="Explanation if this claim conflicts with other captured evidence",
    )


class ContradictionRecord(BaseModel):
    """Documented conflicting evidence points preserved transparently without arbitrary resolution."""

    dimension: str = Field(
        description="Commercial dimension of conflict (e.g., pricing, uptime SLA)"
    )
    entity: str = Field(description="Competitor entity experiencing conflicting claims")
    conflicting_passages: list[dict[str, Any]] = Field(
        description="List of conflicting evidence snippets with source_id and evidence_id"
    )
    resolution_note: str = Field(
        description="Transparent explanation of the discrepancy rather than biased preference"
    )


class CompetitorComparisonItem(BaseModel):
    """Structured entity comparison across standardized market dimensions."""

    competitor_name: str
    pricing_summary: str
    sla_availability: str
    key_features: list[str] = Field(default_factory=list)
    deployment_models: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReportEvaluationMetadata(BaseModel):
    """Compliance and provenance metadata auditing the report's empirical grounding."""

    total_claims: int
    direct_facts_count: int
    inferences_count: int
    recommendations_count: int
    unknowns_count: int
    supported_claims_count: int
    unsupported_claims: list[str] = Field(
        default_factory=list, description="IDs of claims flagged for missing or invalid evidence"
    )
    contradictions_count: int
    grounding_coverage_score: float = Field(
        ge=0.0, le=1.0, description="Ratio of supported factual claims to total factual claims"
    )
    is_valid: bool = Field(
        description="True if zero material factual claims lack supporting evidence"
    )
    reproducibility_hash: str = Field(
        description="Deterministic cryptographic digest of evidence pool and rendered content"
    )


class ValidatedReport(BaseModel):
    """Full validated research report deliverable conforming to Phase 14 specifications."""

    title: str = Field(min_length=5, max_length=255, description="Report title")
    domain: str = Field(description="Market sector analyzed")
    executive_summary: str = Field(min_length=20, description="Executive briefing")
    competitor_comparison: list[CompetitorComparisonItem] = Field(
        default_factory=list, description="Standardized comparison matrix"
    )
    evidence_linked_findings: list[ReportClaim] = Field(
        min_length=1, description="Findings explicitly linked to evidence records"
    )
    positioning_analysis: str = Field(min_length=20, description="Strategic positioning analysis")
    limitations: list[str] = Field(
        default_factory=list, description="Explicit data gaps, unknowns, and freshness boundaries"
    )
    contradictions: list[ContradictionRecord] = Field(
        default_factory=list, description="Preserved evidence contradictions"
    )
    sources: list[SourceRecord] = Field(
        min_length=1, description="Complete bibliography of cited sources"
    )
    retrieval_timestamps: dict[str, str] = Field(
        default_factory=dict, description="Source ID to ISO 8601 retrieval timestamp map"
    )
    evaluation_metadata: ReportEvaluationMetadata = Field(
        description="Audit metadata scoring factual grounding"
    )
    markdown_content: str = Field(
        min_length=50, description="Rendered markdown report with inline citations [E1], [E2]"
    )
