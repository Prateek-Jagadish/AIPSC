"""
services/tagging/chunk_tagging_service.py
──────────────────────────────────────────
Orchestrates the full tagging + embedding pipeline for a document's chunks.

Pipeline for each document:
    1. Load all untagged chunks from DB
    2. Tag each chunk (topic / subtopic / micro_tag via GPT-4o)
    3. Embed each chunk (text-embedding-3-large via OpenAI)
    4. Save tags + embeddings back to DB
    5. Update Document status → Embedded

Called by:
    - document_ingestion_service.py after extraction completes
    - Background task after newspaper ingestion
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from loguru import logger
from datetime import datetime

from app.core.database import AsyncSessionFactory
from app.models.document import Document, Chunk, DocumentStatus
from app.models.user_stats import UserTopicStat, UserMicroTagStat
from app.services.tagging.auto_tagger import tag_chunks_batch
from app.services.tagging.taxonomy_cache import ensure_loaded
from app.services.llm.embeddings import embed_many


# ── Main Service ──────────────────────────────────────────────────────────────

async def tag_and_embed_document(document_id: int) -> bool:
    """
    Full tagging + embedding pipeline for all chunks of a document.

    Steps:
        1. Load chunks for this document
        2. Ensure taxonomy cache is loaded
        3. Tag all chunks in batch
        4. Embed all chunk texts in batch
        5. Save everything back to DB
        6. Update document status → Embedded

    Returns True on success, False on failure.
    """
    async with AsyncSessionFactory() as db:
        try:
            # Load chunks
            result = await db.execute(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.chunk_index)
            )
            chunks = result.scalars().all()

            if not chunks:
                logger.warning(f"No chunks found for document {document_id}")
                return False

            logger.info(f"🏷️  Tagging {len(chunks)} chunks for document {document_id}")

            # Ensure taxonomy is in memory
            await ensure_loaded(db)

            # ── Tag all chunks ─────────────────────────────────────────────
            chunk_texts = [c.text for c in chunks]
            tag_results = await tag_chunks_batch(chunk_texts)

            # ── Embed all chunk texts ──────────────────────────────────────
            logger.info(f"🔢 Embedding {len(chunks)} chunks...")
            embeddings = await embed_many(chunk_texts)

            # ── Save tags + embeddings to DB ───────────────────────────────
            for chunk, tag, embedding in zip(chunks, tag_results, embeddings):
                chunk.topic_id     = tag.topic_id
                chunk.subtopic_id  = tag.subtopic_id
                chunk.micro_tag_id = tag.micro_tag_id
                chunk.tag_confidence = tag.confidence
                chunk.embedding    = embedding

            # ── Update document status ─────────────────────────────────────
            doc_result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = doc_result.scalar_one_or_none()
            if doc:
                doc.status       = DocumentStatus.EMBEDDED
                doc.processed_at = datetime.utcnow()

            await db.commit()

            # ── Update user stats for each tagged topic ────────────────────
            await _update_user_stats_from_chunks(db, tag_results)

            logger.info(
                f"✅ Document {document_id} fully tagged and embedded: "
                f"{len(chunks)} chunks"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Tag+embed pipeline failed for doc {document_id}: {e}")
            return False


# ── User Stats Updater ────────────────────────────────────────────────────────

async def _update_user_stats_from_chunks(db: AsyncSession, tag_results: list) -> None:
    """
    After tagging, updates UserTopicStat and UserMicroTagStat to reflect
    that new content has been added on these topics.

    This does NOT update weakness scores — that's handled by the
    weakness detection service when the user asks for an analysis.
    Here we just make sure the stat records exist and are not flagged
    as "never_touched" anymore.
    """
    seen_topic_ids    = set()
    seen_microtag_ids = set()

    for tag in tag_results:
        if tag.topic_id:
            seen_topic_ids.add(tag.topic_id)
        if tag.micro_tag_id:
            seen_microtag_ids.add(tag.micro_tag_id)

    # Ensure UserTopicStat rows exist
    for topic_id in seen_topic_ids:
        result = await db.execute(
            select(UserTopicStat).where(UserTopicStat.topic_id == topic_id)
        )
        stat = result.scalar_one_or_none()
        if not stat:
            db.add(UserTopicStat(topic_id=topic_id))

    # Ensure UserMicroTagStat rows exist and flip never_touched
    for mt_id in seen_microtag_ids:
        result = await db.execute(
            select(UserMicroTagStat).where(UserMicroTagStat.micro_tag_id == mt_id)
        )
        stat = result.scalar_one_or_none()
        if not stat:
            db.add(UserMicroTagStat(micro_tag_id=mt_id, never_touched=False))
        elif stat.never_touched:
            stat.never_touched = False

    await db.commit()
