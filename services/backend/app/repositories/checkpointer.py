"""Durable LangGraph checkpoint saver backed by PostgreSQL and SQLAlchemy."""

from __future__ import annotations

import base64
import pickle
import uuid
from collections.abc import Sequence
from typing import Any

from langgraph.checkpoint.base import (
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    RunnableConfig,
)
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_sync_session
from app.models.graph_checkpoint import GraphCheckpoint

logger = get_logger("agentops.repositories.checkpointer")


class DurableCheckpointSaver(MemorySaver):
    """Persistent LangGraph checkpointer persisting execution checkpoints to PostgreSQL.

    Guarantees:
    - Survives process crashes and worker restarts.
    - Preserves executed steps, evidence items, and channel versions.
    - Safe resumption using LangGraph Command(resume=...).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def _clean_dicts_for_persistence(
        self, thread_id: str
    ) -> tuple[dict[str, Any], dict[Any, Any], dict[Any, Any]]:
        """Extract and sanitize in-memory storage, writes, and blobs for thread into picklable dicts."""
        storage_clean = {
            k: {ns: dict(chk) for ns, chk in v.items()}
            for k, v in self.storage.items()
            if str(k) == str(thread_id)
        }
        writes_clean = {k: v for k, v in self.writes.items() if str(k[0]) == str(thread_id)}
        blobs_clean = {k: v for k, v in self.blobs.items() if str(k[0]) == str(thread_id)}
        return storage_clean, writes_clean, blobs_clean

    def _persist_to_db(
        self,
        thread_id: str,
        checkpoint_id: str,
        parent_checkpoint_id: str | None = None,
        metadata: CheckpointMetadata | None = None,
        db_session: Session | None = None,
    ) -> None:
        """Serialize thread checkpoint state to the graph_checkpoints database table."""
        try:
            run_uuid = uuid.UUID(thread_id)
        except (ValueError, TypeError):
            # Not a valid UUID thread_id (e.g. test string), skip DB persistence or handle gracefully
            return

        storage_clean, writes_clean, blobs_clean = self._clean_dicts_for_persistence(thread_id)
        blob_bytes = pickle.dumps((storage_clean, writes_clean, blobs_clean))
        encoded_blob = base64.b64encode(blob_bytes).decode("ascii")

        meta_dict = dict(metadata or {})
        # Convert non-serializable metadata values to strings
        safe_meta = {str(k): str(v) for k, v in meta_dict.items()}

        def _do_save(s: Session) -> None:
            # Check if checkpoint already exists for this run_id and checkpoint_id
            stmt = select(GraphCheckpoint).where(
                GraphCheckpoint.run_id == run_uuid,
                GraphCheckpoint.checkpoint_id == str(checkpoint_id),
            )
            existing = s.execute(stmt).scalar_one_or_none()
            if existing:
                existing.checkpoint_blob = encoded_blob
                existing.metadata_payload = safe_meta
            else:
                chk_entity = GraphCheckpoint(
                    run_id=run_uuid,
                    checkpoint_id=str(checkpoint_id),
                    parent_checkpoint_id=str(parent_checkpoint_id)
                    if parent_checkpoint_id
                    else None,
                    checkpoint_type="langgraph",
                    checkpoint_blob=encoded_blob,
                    metadata_payload=safe_meta,
                )
                s.add(chk_entity)
            s.commit()

        try:
            if db_session:
                _do_save(db_session)
            else:
                with get_sync_session() as s:
                    _do_save(s)
            logger.debug(
                "checkpoint_persisted_to_db", run_id=thread_id, checkpoint_id=checkpoint_id
            )
        except Exception as exc:
            logger.warning("checkpoint_db_persist_failed", run_id=thread_id, error=str(exc))

    def _load_from_db(self, thread_id: str, db_session: Session | None = None) -> bool:
        """Load latest serialized checkpoint state from database for given thread_id."""
        try:
            run_uuid = uuid.UUID(thread_id)
        except (ValueError, TypeError):
            return False

        def _do_load(s: Session) -> GraphCheckpoint | None:
            stmt = (
                select(GraphCheckpoint)
                .where(GraphCheckpoint.run_id == run_uuid)
                .order_by(GraphCheckpoint.created_at.desc())
            )
            return s.execute(stmt).scalars().first()

        try:
            if db_session:
                chk = _do_load(db_session)
            else:
                with get_sync_session() as s:
                    chk = _do_load(s)

            if not chk or not chk.checkpoint_blob:
                return False

            blob_bytes = base64.b64decode(chk.checkpoint_blob.encode("ascii"))
            s_dict, w_dict, b_dict = pickle.loads(blob_bytes)

            for k, v in s_dict.items():
                for ns, chks in v.items():
                    self.storage[k][ns].update(chks)
            self.writes.update(w_dict)
            self.blobs.update(b_dict)

            logger.info(
                "checkpoint_loaded_from_db", run_id=thread_id, checkpoint_id=chk.checkpoint_id
            )
            return True
        except Exception as exc:
            logger.warning("checkpoint_db_load_failed", run_id=thread_id, error=str(exc))
            return False

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save checkpoint in memory and persist snapshot to PostgreSQL."""
        result_config = super().put(config, checkpoint, metadata, new_versions)
        thread_id = str(config.get("configurable", {}).get("thread_id", ""))
        checkpoint_id = str(checkpoint.get("id", ""))
        parent_id = config.get("configurable", {}).get("checkpoint_id")
        if thread_id and checkpoint_id:
            self._persist_to_db(thread_id, checkpoint_id, parent_id, metadata)
        return result_config

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Save writes and persist updated snapshot to PostgreSQL."""
        super().put_writes(config, writes, task_id, task_path)
        thread_id = str(config.get("configurable", {}).get("thread_id", ""))
        checkpoint_id = str(config.get("configurable", {}).get("checkpoint_id", ""))
        if thread_id and checkpoint_id:
            self._persist_to_db(thread_id, checkpoint_id)

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Fetch checkpoint tuple, loading from PostgreSQL if thread is not in memory."""
        thread_id = str(config.get("configurable", {}).get("thread_id", ""))
        if thread_id and thread_id not in self.storage:
            self._load_from_db(thread_id)
        return super().get_tuple(config)
