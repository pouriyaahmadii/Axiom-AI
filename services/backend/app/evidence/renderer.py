"""Deterministic markdown report renderer producing verifiable evidence citations and provenance bibliographies."""

from __future__ import annotations

from app.evidence.models import (
    ClaimType,
    CompetitorComparisonItem,
    ContradictionRecord,
    EvidenceRecord,
    ReportClaim,
    ReportEvaluationMetadata,
    SourceRecord,
)


class ReportRenderer:
    """Renders structured intelligence reports into verified, citation-annotated markdown."""

    def render(
        self,
        title: str,
        domain: str,
        executive_summary: str,
        competitor_comparison: list[CompetitorComparisonItem],
        findings: list[ReportClaim],
        positioning_analysis: str,
        limitations: list[str],
        contradictions: list[ContradictionRecord],
        sources: list[SourceRecord],
        evidence: list[EvidenceRecord],
        evaluation_metadata: ReportEvaluationMetadata,
    ) -> str:
        """Render complete markdown document with citation badges [E1], comparison table, and bibliography."""
        # Build evidence-to-alias mapping (E1, E2, ...)
        ev_to_alias: dict[str, str] = {}
        for idx, ev in enumerate(evidence, start=1):
            ev_to_alias[ev.evidence_id] = f"E{idx}"

        lines: list[str] = []

        # Document Header
        lines.append(f"# {title.strip()}")
        lines.append("")
        lines.append(
            f"*Domain: {domain} | Factual Grounding Coverage: {evaluation_metadata.grounding_coverage_score:.1%} | Validated: {'Yes' if evaluation_metadata.is_valid else 'No'}*"
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Section 1: Executive Summary
        lines.append("## 1. Executive Summary")
        lines.append("")
        lines.append(executive_summary.strip())
        lines.append("")

        # Section 2: Competitor Comparison Matrix
        if competitor_comparison:
            lines.append("## 2. Competitor Comparison Matrix")
            lines.append("")
            lines.append(
                "| Competitor | Pricing Summary | SLA & Availability | Key Features | Deployment Models | Limitations |"
            )
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for comp in competitor_comparison:
                features_str = ", ".join(comp.key_features) or "N/A"
                deploy_str = ", ".join(comp.deployment_models) or "N/A"
                limits_str = ", ".join(comp.limitations) or "N/A"
                lines.append(
                    f"| **{comp.competitor_name}** | {comp.pricing_summary} | {comp.sla_availability} | {features_str} | {deploy_str} | {limits_str} |"
                )
            lines.append("")

        # Section 3: Evidence-Linked Findings
        lines.append("## 3. Evidence-Linked Findings")
        lines.append("")
        lines.append(
            "> **Epistemic Classification**: Claims are strictly typed as Direct Facts, Inferences, Recommendations, or Unknowns. Factual claims require verified empirical citations."
        )
        lines.append("")

        for claim in findings:
            badge = self._format_claim_badge(claim.claim_type)
            citations = self._format_citations(claim.evidence_ids, ev_to_alias)
            citations_str = f" {citations}" if citations else ""

            status_warn = ""
            if not claim.is_supported and claim.claim_type == ClaimType.DIRECT_FACT:
                status_warn = " ⚠️ **[UNSUPPORTED CLAIM: Missing Verified Evidence]**"

            contradiction_warn = ""
            if claim.contradiction_notes:
                contradiction_warn = f" ⚠️ *[Contradiction Note: {claim.contradiction_notes}]*"

            confidence_str = f" *(Confidence: {claim.confidence.value})*"

            lines.append(
                f"- {badge} **{claim.entity}**: {claim.statement}{citations_str}{status_warn}{contradiction_warn}{confidence_str}"
            )
        lines.append("")

        # Section 4: Preserved Contradictions & Discrepancies
        if contradictions:
            lines.append("## 4. Preserved Contradictions & Discrepancies")
            lines.append("")
            lines.append(
                "> **Policy**: Conflicting market evidence is preserved transparently rather than biasedly resolved."
            )
            lines.append("")
            lines.append(
                "| Dimension | Entity | Conflicting Evidence Snippets | Discrepancy Analysis |"
            )
            lines.append("| :--- | :--- | :--- | :--- |")
            for contra in contradictions:
                snippets_list = []
                for p in contra.conflicting_passages:
                    snippet_text = p.get("passage", p.get("text", str(p)))
                    snippets_list.append(f'• "{snippet_text}"')
                snippets_str = "<br>".join(snippets_list)
                lines.append(
                    f"| **{contra.dimension}** | {contra.entity} | {snippets_str} | {contra.resolution_note} |"
                )
            lines.append("")

        # Section 5: Strategic Positioning Analysis
        lines.append("## 5. Strategic Positioning Analysis")
        lines.append("")
        lines.append(positioning_analysis.strip())
        lines.append("")

        # Section 6: Limitations & Unknowns
        lines.append("## 6. Limitations, Unknowns & Freshness Boundaries")
        lines.append("")
        # Add explicit limitations
        for limit in limitations:
            lines.append(f"- {limit}")

        # Add explicit UNKNOWN claims to limitations
        unknown_claims = [c for c in findings if c.claim_type == ClaimType.UNKNOWN]
        if unknown_claims:
            for unc in unknown_claims:
                lines.append(f"- **Data Gap**: {unc.entity} - {unc.statement}")
        lines.append("")

        # Section 7: Sources & Provenance Bibliography
        lines.append("## 7. Sources & Provenance Bibliography")
        lines.append("")
        if evidence:
            lines.append(
                "| Citation | Evidence ID | Source ID | Entity | Publisher / URL | Content SHA-256 | Status |"
            )
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            # Map source_id to source record
            sources_map = {s.source_id: s for s in sources}
            for ev in evidence:
                alias = f"**[{ev_to_alias.get(ev.evidence_id, 'E?')}]**"
                src = sources_map.get(ev.source_id)
                url_display = f"[{src.publisher_or_host}]({src.url})" if src else "Unknown Source"
                hash_short = f"`{ev.content_hash[:12]}...`"
                status_str = ev.validation_status.value.upper()
                lines.append(
                    f"| {alias} | `{ev.evidence_id}` | `{ev.source_id}` | {ev.related_entity} | {url_display} | {hash_short} | {status_str} |"
                )
        else:
            lines.append("*No empirical evidence records captured for this deliverable.*")
        lines.append("")

        # Section 8: Provenance & Grounding Audit
        lines.append("## 8. Provenance & Reproducibility Audit")
        lines.append("")
        lines.append(f"- **Total Epistemic Claims**: {evaluation_metadata.total_claims}")
        lines.append(
            f"  - Direct Empirical Facts: {evaluation_metadata.direct_facts_count} (Supported: {evaluation_metadata.direct_facts_count - len(evaluation_metadata.unsupported_claims)})"
        )
        lines.append(f"  - Analytical Inferences: {evaluation_metadata.inferences_count}")
        lines.append(f"  - Recommendations: {evaluation_metadata.recommendations_count}")
        lines.append(f"  - Unknowns / Disclosed Gaps: {evaluation_metadata.unknowns_count}")
        lines.append(
            f"- **Grounding Coverage Score**: {evaluation_metadata.grounding_coverage_score:.1%}"
        )
        lines.append(
            f"- **Audited Integrity Status**: {'VALID' if evaluation_metadata.is_valid else 'FLAGGED_UNSUPPORTED'}"
        )
        lines.append(
            f"- **Reproducibility Digest (SHA-256)**: `{evaluation_metadata.reproducibility_hash}`"
        )
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_claim_badge(claim_type: ClaimType) -> str:
        """Render badge for epistemic claim type."""
        badges = {
            ClaimType.DIRECT_FACT: "`[DIRECT FACT]`",
            ClaimType.INFERENCE: "`[INFERENCE]`",
            ClaimType.RECOMMENDATION: "`[RECOMMENDATION]`",
            ClaimType.UNKNOWN: "`[UNKNOWN]`",
        }
        return badges.get(claim_type, "`[CLAIM]`")

    @staticmethod
    def _format_citations(evidence_ids: list[str], ev_to_alias: dict[str, str]) -> str:
        """Format citation marker list [E1, E2]."""
        if not evidence_ids:
            return ""
        markers = [f"[{ev_to_alias.get(eid, eid)}]" for eid in evidence_ids]
        return "".join(markers)
