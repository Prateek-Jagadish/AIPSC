"""
app/worker.py
──────────────
Celery worker configuration for background processing tasks.

Tasks:
    - process_document_task    → OCR + extract + chunk + tag + embed
    - process_newspaper_task   → filter + tag + embed newspaper articles
    - process_visuals_task     → AI caption all images in a document
    - recompute_weakness_task  → recalculate weakness scores

Start worker:
    celery -A app.worker worker --loglevel=info
"""

from celery import Celery
from loguru import logger
import asyncio

from app.core.config import settings

# ── Celery App ─────────────────────────────────────────────────────────────

celery_app = Celery(
    "upsc_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,    # one task at a time (OCR is CPU heavy)
    task_acks_late=True,
)


# ── Helper ─────────────────────────────────────────────────────────────────

def run_async(coro):
    """Run an async function from a sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Tasks ──────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="process_document", max_retries=2)
def process_document_task(self, document_id: int):
    """Full ingestion pipeline for a PDF document."""
    try:
        from app.services.ingestion.document_ingestion_service import process_document
        from app.services.tagging.chunk_tagging_service import tag_and_embed_document
        from app.core.database import AsyncSessionFactory

        async def _run():
            async with AsyncSessionFactory() as db:
                await process_document(db, document_id)
            await tag_and_embed_document(document_id)

        run_async(_run())
        logger.info(f"✅ Document {document_id} processed")

    except Exception as exc:
        logger.error(f"❌ Document {document_id} failed: {exc}")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, name="process_newspaper", max_retries=2)
def process_newspaper_task(self, document_id: int):
    """Newspaper article extraction + UPSC filtering pipeline."""
    try:
        from app.services.ingestion.newspaper_pipeline import process_newspaper
        from app.core.database import AsyncSessionFactory

        async def _run():
            async with AsyncSessionFactory() as db:
                return await process_newspaper(db, document_id)

        result = run_async(_run())
        logger.info(f"✅ Newspaper {document_id}: {result}")

    except Exception as exc:
        logger.error(f"❌ Newspaper {document_id} failed: {exc}")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, name="process_visuals", max_retries=1)
def process_visuals_task(self, document_id: int):
    """AI captioning for all visual assets in a document."""
    try:
        from app.services.intelligence.visual_intelligence_service import process_document_visuals
        result = run_async(process_document_visuals(document_id))
        logger.info(f"✅ Visuals {document_id}: {result}")

    except Exception as exc:
        logger.error(f"❌ Visuals {document_id} failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="recompute_weakness")
def recompute_weakness_task():
    """Recalculates weakness scores for all topics. Run nightly."""
    from app.services.intelligence.weakness_detection_service import compute_weakness_report
    from app.core.database import AsyncSessionFactory

    async def _run():
        async with AsyncSessionFactory() as db:
            return await compute_weakness_report(db)

    run_async(_run())
    logger.info("✅ Weakness scores recomputed")


# ── Periodic Tasks ─────────────────────────────────────────────────────────

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # Recompute weakness scores every night at 11pm IST
    "nightly-weakness-recompute": {
        "task":     "recompute_weakness",
        "schedule": crontab(hour=23, minute=0),
    },
}
