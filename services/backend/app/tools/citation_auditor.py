"""Citation grounding auditor verifying empirical evidence links and detecting hallucinations."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.tools.evidence import EvidenceService

logger = get_logger("agentops.tools.citation_auditor")

# Regex to detect citation markers in markdown reports:
# e.g., [E1], [E2], [ev-a1b2c3d4e5f6], or [Source Title](https://example.com...)
CITATION_MARKER_PATTERN = re.compile(r"\[(E\d+|ev-[a-f0-9]{8,12}|source-\d+)\]", re.IGNORECASE)


class CitationAuditResult(BaseModel):
    """Result of auditing report citations against captured empirical evidence."""

    is_grounded: bool = Field(
        description="Whether all cited claims map to verified evidence records"
    )
    total_citations_found: int = Field(
        default=0, description="Total count of citation markers identified"
    )
    verified_citations_count: int = Field(
        default=0, description="Count of citations matching valid evidence records"
    )
    hallucinated_citations: list[str] = Field(
        default_factory=list, description="Citation markers referencing missing or invalid evidence"
    )
    coverage_score: float = Field(default=1.0, description="Grounding coverage ratio (0.0 to 1.0)")
    grounded_evidence_ids: list[str] = Field(
        default_factory=list, description="List of verified evidence IDs referenced"
    )
    audit_notes: list[str] = Field(
        default_factory=list, description="Detailed explanatory audit findings"
    )


class CitationAuditor:
    """Audits report deliverables to ensure strict grounding in empirical evidence."""

    @classmethod
    def extract_citations_from_markdown(cls, markdown_text: str) -> list[str]:
        """Extract all citation markers from markdown report content."""
        if not markdown_text:
            return []

        markers = CITATION_MARKER_PATTERN.findall(markdown_text)
        return list(dict.fromkeys(markers))  # preserve order, deduplicate

    @classmethod
    def audit_report_grounding(
        cls,
        report_data: dict[str, Any],
        evidence_items: list[dict[str, Any]],
    ) -> CitationAuditResult:
        """Audit report claims and citations against the recorded evidence pool."""
        markdown = report_data.get("markdown_content", "")
        explicit_citations = report_data.get("citations", [])

        # Extract citation markers from markdown text
        found_markers = cls.extract_citations_from_markdown(markdown)

        # Index available evidence by various keys: evidence_id, short hash, source URL, marker alias
        evidence_by_id: dict[str, dict[str, Any]] = {}
        evidence_by_hash: dict[str, dict[str, Any]] = {}
        evidence_by_url: dict[str, dict[str, Any]] = {}
        evidence_by_alias: dict[str, dict[str, Any]] = {}

        for idx, ev in enumerate(evidence_items, start=1):
            ev_id = ev.get("evidence_id") or f"ev-{ev.get('content_hash', '')[:12]}"
            content_hash = ev.get("content_hash", "")
            source_url = ev.get("source_url", "")
            alias = f"E{idx}"

            evidence_by_id[ev_id.lower()] = ev
            if content_hash:
                evidence_by_hash[content_hash.lower()] = ev
                evidence_by_hash[content_hash[:12].lower()] = ev
            if source_url:
                evidence_by_url[source_url.lower()] = ev
            evidence_by_alias[alias.lower()] = ev

        verified_ids: set[str] = set()
        hallucinated: list[str] = []
        audit_notes: list[str] = []

        # Audit markers found in text
        for marker in found_markers:
            marker_key = marker.lower()
            matched_ev: dict[str, Any] | None = (
                evidence_by_alias.get(marker_key)
                or evidence_by_id.get(marker_key)
                or evidence_by_hash.get(marker_key)
            )

            if matched_ev:
                # Verify cryptographic integrity of the matched evidence
                if EvidenceService.verify_evidence_integrity(matched_ev):
                    ev_id = matched_ev.get("evidence_id", marker)
                    verified_ids.add(ev_id)
                else:
                    hallucinated.append(f"{marker} (tampered content hash)")
                    audit_notes.append(
                        f"Citation [{marker}] points to evidence with a mismatched SHA-256 hash."
                    )
            else:
                hallucinated.append(marker)
                audit_notes.append(
                    f"Citation [{marker}] has no corresponding record in the captured evidence pool."
                )

        # Audit structured citations list in report metadata
        for cit in explicit_citations:
            ev_id = cit.get("evidence_id", "") if isinstance(cit, dict) else str(cit)
            if not ev_id:
                continue

            ev_key = ev_id.lower()
            matched_ev = (
                evidence_by_id.get(ev_key)
                or evidence_by_hash.get(ev_key)
                or evidence_by_alias.get(ev_key)
            )

            if matched_ev:
                verified_ids.add(matched_ev.get("evidence_id", ev_id))
            else:
                if ev_id not in hallucinated:
                    hallucinated.append(ev_id)
                    audit_notes.append(
                        f"Structured citation '{ev_id}' not found in run evidence records."
                    )

        total_citations = len(found_markers) + (len(explicit_citations) if not found_markers else 0)
        verified_count = len(verified_ids)

        # Calculate coverage score
        if total_citations == 0:
            # If report has empirical claims but no citations, warn
            if len(evidence_items) > 0 and len(markdown) > 200:
                coverage_score = 0.5
                audit_notes.append(
                    "Report synthesized with available evidence but omitted explicit inline citation markers."
                )
            else:
                coverage_score = 1.0
        else:
            coverage_score = round(verified_count / max(total_citations, 1), 2)

        is_grounded = len(hallucinated) == 0

        logger.info(
            "citation_audit_completed",
            is_grounded=is_grounded,
            total_citations=total_citations,
            verified_count=verified_count,
            hallucinated_count=len(hallucinated),
            coverage_score=coverage_score,
        )

        return CitationAuditResult(
            is_grounded=is_grounded,
            total_citations_found=total_citations,
            verified_citations_count=verified_count,
            hallucinated_citations=hallucinated,
            coverage_score=coverage_score,
            grounded_evidence_ids=sorted(verified_ids),
            audit_notes=audit_notes,
        )
