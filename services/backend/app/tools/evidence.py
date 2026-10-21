"""Evidence provenance service for tracking, hashing, and validating empirical research facts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.evidence.models import (
    ClaimType,
    EvidenceRecord,
    ExtractionStatus,
    ReportClaim,
    RetrievalStatus,
    SourceRecord,
    SourceType,
    ValidationStatus,
)
from app.evidence.pipeline import EvidencePipeline


class EvidenceService:
    """Manages the lifecycle and cryptographic integrity of empirical evidence records."""

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize whitespace and control characters to produce canonical text for hashing."""
        return EvidencePipeline.normalize_text(text)

    @classmethod
    def compute_content_hash(cls, text: str) -> str:
        """Compute a deterministic SHA-256 hash of normalized text snippet."""
        return EvidencePipeline.compute_sha256(text)

    @classmethod
    def create_evidence_record(
        cls,
        run_id: str,
        step_identifier: str,
        tool_name: str,
        source_url: str,
        snippet: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a verifiable evidence record anchored to a source URL and content hash."""
        clean_snippet = cls.normalize_text(snippet)
        content_hash = cls.compute_content_hash(clean_snippet)
        short_id = content_hash[:12]

        return {
            "evidence_id": f"ev-{short_id}",
            "run_id": run_id,
            "step_identifier": step_identifier,
            "tool_name": tool_name,
            "source_url": source_url,
            "content_hash": content_hash,
            "snippet": clean_snippet,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def verify_evidence_integrity(cls, evidence_record: dict[str, Any]) -> bool:
        """Verify that an evidence record's snippet matches its recorded SHA-256 hash."""
        snippet = evidence_record.get("snippet", "")
        recorded_hash = evidence_record.get("content_hash", "")
        if not snippet or not recorded_hash:
            return False

        expected_hash = cls.compute_content_hash(str(snippet))
        return bool(expected_hash == str(recorded_hash))


__all__ = [
    "ClaimType",
    "EvidencePipeline",
    "EvidenceRecord",
    "EvidenceService",
    "ExtractionStatus",
    "ReportClaim",
    "RetrievalStatus",
    "SourceRecord",
    "SourceType",
    "ValidationStatus",
]
