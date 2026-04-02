"""
services/ingestion/document_ingestion_service.py
──────────────────────────────────────────────────
The main ingestion orchestrator. Coordinates the full pipeline:

    Upload → Save → Extract → Chunk → Tag → Save to DB → Embed

This is what the upload API endpoint calls.
It returns immediately with a document_id and kicks off processing
as a background job (Celery task).

Pipeline stages:
    Stage 1 — Receive file, save to disk, create Document record (FAST)
    Stage 2 — Extract text + images via pdf_processor        (SLOW, background)
    Stage 3 — Chunk text via chunker                          (MEDIUM, background)
    Stage 4 — Auto-tag chunks via tagging service             (SLOW, background)
    Stage 5 — Generate embeddings via LLM service             (SLOW, background)
    Stage 6 — Store chunks + images in DB with embeddings     (MEDIUM, background)
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from loguru import logger

from app.core.config import settings
from app.models.document import Document, Chunk, DocumentType, DocumentStatus, PDFType
from app.models.visual_asset import VisualAsset, ImageType, ExamUse
from app.services.ingestion.pdf_processor import extract_pdf
from app.services.ingestion.chunker import chunk_document_pages
from app.services.ingestion.file_storage import (
    save_uploaded_pdf, save_image, get_file_size_kb
)


# ── Stage 1: Receive & Register ───────────────────────────────────────────────

async def register_document(
    db: AsyncSession,
    file_bytes: bytes,
    original_filename: str,
    doc_type: DocumentType,
    metadata: dict = None,
) -> Document:
    """
    Stage 1 — Fast path (runs synchronously before returning to the user):
        1. Save file to disk
        2. Create Document record in DB with status=UPLOADED
        3. Return Document object with its new ID

    The heavy processing happens in Stage 2+ (background task).
    """
    metadata = metadata or {}

    # Save file
    file_path = save_uploaded_pdf(file_bytes, original_filename, doc_type)
    file_size = get_file_size_kb(file_path)

    # Create DB record
    doc = Document(
        title=metadata.get("title", original_filename),
        source_type=doc_type,
        status=DocumentStatus.UPLOADED,
        file_path=file_path,
        file_size_kb=file_size,

        # PYQ metadata
        year=metadata.get("year"),
        paper=metadata.get("paper"),

        # Newspaper metadata
        publication=metadata.get("publication"),
        publish_date=metadata.get("publish_date"),

        # Book/NCERT metadata
        subject=metadata.get("subject"),
        class_level=metadata.get("class_level"),
    )

    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    logger.info(f"📋 Document registered: id={doc.id} | {doc.title} | {doc_type}")
    return doc


# ── Stage 2–6: Full Processing Pipeline ──────────────────────────────────────

async def process_document(
    db: AsyncSession,
    document_id: int,
) -> bool:
    """
    Stages 2–6 — Full processing pipeline.
    Meant to run as a background task after register_document().

    Steps:
        2. Extract PDF (OCR + text + images)
        3. Chunk text
        4. Classify image types (basic heuristic, full AI caption in visual service)
        5. Save chunks to DB
        6. Save visual assets to DB
        7. Update document status

    Note: embedding generation is handled separately by the embedding service
    after this function completes (to allow batch embedding calls).
    """
    # Load document
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        logger.error(f"Document {document_id} not found")
        return False

    try:
        # ── Update status → PROCESSING ────────────────────────────────────
        doc.status = DocumentStatus.PROCESSING
        await db.commit()

        # ── Stage 2: Extract PDF ──────────────────────────────────────────
        logger.info(f"⚙️  Processing document {document_id}: {doc.title}")
        extraction = extract_pdf(doc.file_path)

        if extraction.error:
            logger.warning(f"⚠️  Extraction had errors: {extraction.error}")

        # Update PDF type on document
        doc.pdf_type    = PDFType(extraction.pdf_type)
        doc.ocr_applied = extraction.ocr_applied
        doc.page_count  = extraction.total_pages
        await db.commit()

        # ── Stage 3: Chunk text ───────────────────────────────────────────
        text_chunks = chunk_document_pages(extraction.pages)
        doc.chunk_count = len(text_chunks)

        # ── Stage 4: Save chunks to DB (untagged first) ───────────────────
        for tc in text_chunks:
            chunk = Chunk(
                document_id=document_id,
                text=tc.text,
                page_number=tc.page_number,
                chunk_index=tc.chunk_index,
                token_count=tc.token_count,
                # topic/subtopic/micro_tag filled by tagging service later
                # embedding filled by embedding service later
            )
            db.add(chunk)

        await db.flush()   # persist chunks, get IDs

        # ── Stage 5: Save visual assets ───────────────────────────────────
        image_count = 0
        for page in extraction.pages:
            for img in page.images:
                # Save image bytes to disk
                img_path = save_image(
                    image_bytes=img.image_bytes,
                    document_id=document_id,
                    page_number=img.page_number,
                    image_index=img.image_index,
                )

                # Basic image type heuristic (AI classification happens in visual service)
                guessed_type = _guess_image_type(img.ocr_text, img.surrounding_text)

                visual = VisualAsset(
                    document_id=document_id,
                    page_number=img.page_number,
                    image_index=img.image_index,
                    image_path=img_path,
                    image_format="png",
                    width_px=img.width,
                    height_px=img.height,
                    ocr_text=img.ocr_text or None,
                    surrounding_text=img.surrounding_text or None,
                    image_type=guessed_type,
                    # ai_caption + embedding filled by visual service later
                )
                db.add(visual)
                image_count += 1

        doc.image_count = image_count
        doc.status = DocumentStatus.TAGGED   # ready for tagging + embedding
        doc.processed_at = datetime.utcnow()

        await db.commit()

        # ── Stage 6: Kick off tagging + embedding ──────────────────────────
        # (runs async after this function returns)
        from app.services.tagging.chunk_tagging_service import tag_and_embed_document
        import asyncio
        asyncio.create_task(tag_and_embed_document(document_id))

        # ── Stage 7: Kick off visual captioning (if images were extracted) ─
        # Uses GPT-4o Vision to classify each image (Map/Table/Graph/etc.),
        # generate UPSC-focused AI captions, and embed them into pgvector
        # so maps/diagrams become retrievable alongside text.
        if image_count > 0:
            from app.services.intelligence.visual_intelligence_service import process_document_visuals
            asyncio.create_task(process_document_visuals(document_id))
            logger.info(f"🖼️  Visual captioning queued for {image_count} images")

        logger.info(
            f"✅ Document {document_id} processed: "
            f"{len(text_chunks)} chunks | {image_count} images"
        )
        return True

    except Exception as e:
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(e)
        await db.commit()
        logger.error(f"❌ Processing failed for document {document_id}: {e}")
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _guess_image_type(ocr_text: str, surrounding_text: str) -> ImageType:
    """
    Quick heuristic to guess image type from surrounding text and OCR labels.
    Used before the full AI classification step.
    Full AI classification happens in visual_intelligence_service.py.
    """
    combined = f"{ocr_text} {surrounding_text}".lower()

    if any(kw in combined for kw in ["map", "region", "state", "district", "river",
                                      "latitude", "longitude", "location", "geography"]):
        return ImageType.MAP

    if any(kw in combined for kw in ["table", "sr.no", "s.no", "column", "row",
                                      "comparison", "list", "year"]):
        return ImageType.TABLE

    if any(kw in combined for kw in ["graph", "chart", "axis", "x-axis", "y-axis",
                                      "trend", "growth", "gdp", "percent"]):
        return ImageType.GRAPH

    if any(kw in combined for kw in ["flow", "diagram", "process", "step", "stage",
                                      "cycle", "structure", "framework"]):
        return ImageType.DIAGRAM

    if any(kw in combined for kw in ["figure", "photo", "image", "picture"]):
        return ImageType.PHOTO

    return ImageType.OTHER
