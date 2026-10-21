"""Persistence service for storing and retrieving sources, evidence records, and validated reports in PostgreSQL."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.evidence.models import ValidatedReport
from app.evidence.pipeline import EvidencePipeline
from app.models.evidence import EvidenceItem
from app.models.report import Report
from app.models.source import Source

logger = get_logger("agentops.evidence.service")


class EvidencePersistenceService:
    """Bridges in-memory evidence pipelines with relational PostgreSQL persistence."""

    @classmethod
    async def persist_pipeline_bundle(
        cls,
        session: AsyncSession,
        run_id: uuid.UUID,
        pipeline: EvidencePipeline,
        report: ValidatedReport | None = None,
    ) -> tuple[list[Source], list[EvidenceItem], Report | None]:
        """Persist all sources, evidence excerpts, and the finalized report atomically."""
        persisted_sources: list[Source] = []
        source_id_to_db_id: dict[str, uuid.UUID] = {}

        # 1. Persist Source records
        for src_record in pipeline.list_sources():
            src_stmt = select(Source).where(Source.run_id == run_id, Source.url == src_record.url)
            src_result = await session.execute(src_stmt)
            existing_src = src_result.scalar_one_or_none()

            if existing_src:
                source_id_to_db_id[src_record.source_id] = existing_src.id
                persisted_sources.append(existing_src)
            else:
                db_source = Source(
                    run_id=run_id,
                    url=src_record.url,
                    domain=src_record.publisher_or_host,
                    title=src_record.title,
                    content_hash=src_record.content_hash,
                    retrieved_at=src_record.retrieved_at,
                )
                session.add(db_source)
                await session.flush()
                source_id_to_db_id[src_record.source_id] = db_source.id
                persisted_sources.append(db_source)

        # 2. Persist Evidence items
        persisted_evidence: list[EvidenceItem] = []
        for ev_record in pipeline.list_evidence():
            ev_stmt = select(EvidenceItem).where(
                EvidenceItem.run_id == run_id,
                EvidenceItem.content_hash == ev_record.content_hash,
            )
            ev_result = await session.execute(ev_stmt)
            existing_ev = ev_result.scalar_one_or_none()

            if existing_ev:
                persisted_evidence.append(existing_ev)
            else:
                db_source_id = source_id_to_db_id.get(ev_record.source_id)
                src = pipeline.get_source(ev_record.source_id)
                source_url = src.url if src else "unknown"

                ev_metadata = {
                    "related_entity": ev_record.related_entity,
                    "related_claim": ev_record.related_claim,
                    "extraction_status": ev_record.extraction_status.value,
                    "validation_status": ev_record.validation_status.value,
                    "custom": ev_record.metadata,
                }

                db_ev = EvidenceItem(
                    run_id=run_id,
                    source_id=db_source_id,
                    source_url=source_url,
                    content_hash=ev_record.content_hash,
                    raw_snippet=ev_record.extracted_passage,
                    metadata_payload=ev_metadata,
                )
                session.add(db_ev)
                await session.flush()
                persisted_evidence.append(db_ev)

        # 3. Persist Validated Report if provided
        persisted_report: Report | None = None
        if report:
            report_stmt = select(Report).where(Report.run_id == run_id)
            report_result = await session.execute(report_stmt)
            existing_report = report_result.scalar_one_or_none()

            citations_payload = [
                {
                    "claim_id": c.claim_id,
                    "claim_type": c.claim_type.value,
                    "entity": c.entity,
                    "statement": c.statement,
                    "evidence_ids": c.evidence_ids,
                    "is_supported": c.is_supported,
                }
                for c in report.evidence_linked_findings
            ]

            report_metadata: dict[str, Any] = {
                "domain": report.domain,
                "evaluation_metadata": report.evaluation_metadata.model_dump(),
                "retrieval_timestamps": report.retrieval_timestamps,
                "contradictions": [c.model_dump() for c in report.contradictions],
                "competitor_comparison": [c.model_dump() for c in report.competitor_comparison],
                "limitations": report.limitations,
            }

            if existing_report:
                existing_report.title = report.title
                existing_report.markdown_content = report.markdown_content
                existing_report.executive_summary = report.executive_summary
                existing_report.citations = citations_payload
                existing_report.metadata_payload = report_metadata
                persisted_report = existing_report
            else:
                db_report = Report(
                    run_id=run_id,
                    title=report.title,
                    markdown_content=report.markdown_content,
                    executive_summary=report.executive_summary,
                    citations=citations_payload,
                    metadata_payload=report_metadata,
                )
                session.add(db_report)
                await session.flush()
                persisted_report = db_report

        logger.info(
            "pipeline_bundle_persisted",
            run_id=str(run_id),
            sources_count=len(persisted_sources),
            evidence_count=len(persisted_evidence),
            has_report=bool(persisted_report),
        )
        return persisted_sources, persisted_evidence, persisted_report
