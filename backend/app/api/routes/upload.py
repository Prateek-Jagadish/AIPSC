"""
api/routes/upload.py
────────────────────
Upload endpoints for all file types.

Endpoints:
    POST /upload/pdf         — PYQs, NCERTs, books, notes, syllabus
    POST /upload/newspaper   — Daily newspaper PDF
    POST /upload/json        — PYQ JSON with model answers
    GET  /upload/status/{id} — Check processing progress
    GET  /upload/documents   — List all uploaded documents
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from loguru import logger
import json

from app.core.database import get_db
from app.models.document import Document, DocumentType, DocumentStatus
from app.services.ingestion.document_ingestion_service import (
    register_document,
    process_document,
)
from app.core.rate_limiter import limiter, RATE_UPLOAD, RATE_READ

router = APIRouter()

ALLOWED_PDF_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE_MB = 100


# ── Celery Auto-Detection ─────────────────────────────────────────────────────

def _celery_available() -> bool:
    """Check if Celery/Redis is reachable. Cached after first check."""
    if not hasattr(_celery_available, "_ok"):
        try:
            from app.worker import celery_app
            celery_app.connection().ensure_connection(max_retries=1, timeout=2)
            _celery_available._ok = True
            logger.info("✅ Celery/Redis detected — using task queue")
        except Exception:
            _celery_available._ok = False
            logger.info("⚠️  Celery/Redis unavailable — using BackgroundTasks fallback")
    return _celery_available._ok


def _dispatch_task(
    background_tasks: BackgroundTasks,
    celery_task_name: str,
    async_fallback,
    document_id: int,
):
    """Dispatch to Celery if available, otherwise use FastAPI BackgroundTasks."""
    if _celery_available():
        from app.worker import celery_app
        celery_app.send_task(celery_task_name, args=[document_id])
        logger.info(f"📦 Celery task '{celery_task_name}' dispatched for doc_id={document_id}")
    else:
        background_tasks.add_task(async_fallback, document_id)
        logger.info(f"📋 BackgroundTask fallback for doc_id={document_id}")


# ── Response Schemas ──────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    document_id: int
    title: str
    status: str
    message: str


class DocumentStatusResponse(BaseModel):
    document_id:   int
    title:         str
    status:        str
    pdf_type:      Optional[str] = None
    page_count:    Optional[int] = None
    chunk_count:   int = 0
    image_count:   int = 0
    ocr_applied:   bool = False
    processed_at:  Optional[str] = None
    error_message: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def validate_pdf_upload(file: UploadFile, file_bytes: bytes):
    if not file.filename.lower().endswith(".pdf"):
        if file.content_type not in {"application/pdf", "application/octet-stream"}:
            raise HTTPException(400, f"Only PDF files are accepted.")
    if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_FILE_SIZE_MB} MB limit.")


async def _bg_process(document_id: int):
    """Background wrapper around process_document."""
    from app.core.database import AsyncSessionFactory
    async with AsyncSessionFactory() as db:
        await process_document(db, document_id)


async def _bg_process_newspaper(document_id: int):
    """Background wrapper for the newspaper-specific pipeline.

    Unlike _bg_process (which runs the generic PDF pipeline),
    this calls newspaper_pipeline.process_newspaper() which:
        1. Splits the newspaper text into candidate articles
        2. Filters only UPSC-relevant articles using GPT-4o
        3. Creates CurrentAffair records (not generic Chunks)
        4. Tags each article to the syllabus taxonomy
        5. Generates probable question angles
        6. Embeds summaries into pgvector
    """
    from app.core.database import AsyncSessionFactory
    from app.services.ingestion.newspaper_pipeline import process_newspaper
    async with AsyncSessionFactory() as db:
        await process_newspaper(db, document_id)


# ── POST /upload/pdf ──────────────────────────────────────────────────────────

@router.post("/pdf", response_model=UploadResponse)
@limiter.limit(RATE_UPLOAD)
async def upload_pdf(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: str  = Form(default="Notes"),
    title: Optional[str]  = Form(default=None),
    year: Optional[int]   = Form(default=None),
    paper: Optional[str]  = Form(default=None),
    subject: Optional[str] = Form(default=None),
    class_level: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload any PDF: PYQ / NCERT / Book / Notes / Syllabus.
    Returns immediately. Processing runs in the background.
    """
    file_bytes = await file.read()
    validate_pdf_upload(file, file_bytes)

    try:
        document_type = DocumentType(doc_type)
    except ValueError:
        document_type = DocumentType.OTHER

    doc = await register_document(
        db=db,
        file_bytes=file_bytes,
        original_filename=file.filename,
        doc_type=document_type,
        metadata={
            "title": title or file.filename,
            "year": year,
            "paper": paper,
            "subject": subject,
            "class_level": class_level,
        },
    )

    _dispatch_task(background_tasks, "process_document", _bg_process, doc.id)
    logger.info(f"📤 PDF queued: doc_id={doc.id} | {doc.title}")

    return UploadResponse(
        document_id=doc.id,
        title=doc.title,
        status=doc.status.value,
        message=f"Queued for processing. Track at GET /upload/status/{doc.id}",
    )


# ── POST /upload/newspaper ────────────────────────────────────────────────────

@router.post("/newspaper", response_model=UploadResponse)
@limiter.limit(RATE_UPLOAD)
async def upload_newspaper(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    publication: Optional[str] = Form(default="The Hindu"),
    publish_date: Optional[str] = Form(default=None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload today's newspaper PDF.
    The system filters UPSC-relevant articles, summarizes, tags, and stores them.
    """
    file_bytes = await file.read()
    validate_pdf_upload(file, file_bytes)

    parsed_date = datetime.utcnow()
    if publish_date:
        try:
            parsed_date = datetime.strptime(publish_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")

    title = f"{publication} — {parsed_date.strftime('%d %b %Y')}"

    doc = await register_document(
        db=db,
        file_bytes=file_bytes,
        original_filename=file.filename,
        doc_type=DocumentType.NEWSPAPER,
        metadata={"title": title, "publication": publication, "publish_date": parsed_date},
    )

    _dispatch_task(background_tasks, "process_newspaper", _bg_process_newspaper, doc.id)
    logger.info(f"📰 Newspaper queued for UPSC filtering: doc_id={doc.id} | {title}")

    return UploadResponse(
        document_id=doc.id,
        title=doc.title,
        status=doc.status.value,
        message=f"Newspaper queued for UPSC filtering. Track at GET /upload/status/{doc.id}",
    )


# ── POST /upload/json ─────────────────────────────────────────────────────────

@router.post("/json", response_model=UploadResponse)
@limiter.limit(RATE_UPLOAD)
async def upload_pyq_json(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload PYQ JSON file (2016–2025 model answers)."""
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(400, "Only .json files accepted.")

    file_bytes = await file.read()
    try:
        json.loads(file_bytes)   # validate JSON
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

    doc = await register_document(
        db=db,
        file_bytes=file_bytes,
        original_filename=file.filename,
        doc_type=DocumentType.JSON,
        metadata={"title": f"PYQ JSON — {file.filename}"},
    )

    # Trigger PYQ ingestion in background
    async def _ingest_pyq():
        from app.services.intelligence.pyq_ingestion_service import ingest_pyq_json
        await ingest_pyq_json(doc.id, file_bytes)

    background_tasks.add_task(_ingest_pyq)
    logger.info(f"📄 JSON upload accepted: doc_id={doc.id}")

    return UploadResponse(
        document_id=doc.id,
        title=doc.title,
        status=doc.status.value,
        message=f"JSON received. PYQ ingestion will be queued. Track at GET /upload/status/{doc.id}",
    )


# ── GET /upload/status/{document_id} ─────────────────────────────────────────

@router.get("/status/{document_id}", response_model=DocumentStatusResponse)
@limiter.limit(RATE_READ)
async def get_document_status(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Poll the processing status of an uploaded document."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, f"Document {document_id} not found.")

    return DocumentStatusResponse(
        document_id=doc.id,
        title=doc.title,
        status=doc.status.value,
        pdf_type=doc.pdf_type.value if doc.pdf_type else None,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count or 0,
        image_count=doc.image_count or 0,
        ocr_applied=doc.ocr_applied or False,
        processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
        error_message=doc.error_message,
    )


# ── GET /upload/documents ─────────────────────────────────────────────────────

@router.get("/documents")
@limiter.limit(RATE_READ)
async def list_documents(
    request: Request,
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded documents with optional type/status filtering."""
    query = select(Document).order_by(Document.upload_date.desc())

    if doc_type:
        try:
            query = query.where(Document.source_type == DocumentType(doc_type))
        except ValueError:
            pass
    if status:
        try:
            query = query.where(Document.status == DocumentStatus(status))
        except ValueError:
            pass

    query = query.offset(offset).limit(limit)
    docs  = (await db.execute(query)).scalars().all()

    return {
        "total": len(docs),
        "documents": [
            {
                "id":          d.id,
                "title":       d.title,
                "type":        d.source_type.value,
                "status":      d.status.value,
                "pages":       d.page_count,
                "chunks":      d.chunk_count,
                "images":      d.image_count,
                "uploaded_at": d.upload_date.isoformat() if d.upload_date else None,
            }
            for d in docs
        ],
    }
