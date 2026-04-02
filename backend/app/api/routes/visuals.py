"""
api/routes/visuals.py
──────────────────────
Endpoints for visual assets (maps, tables, diagrams, graphs).

Endpoints:
    GET  /visuals/document/{doc_id}   — all visuals from a document
    GET  /visuals/topic/{topic_id}    — visuals for a topic
    GET  /visuals/{visual_id}         — single visual with full metadata
    GET  /visuals/{visual_id}/image   — serve the raw image file
    POST /visuals/{visual_id}/process — manually trigger AI captioning
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
from typing import Optional
from loguru import logger

from app.core.database import get_db
from app.models.visual_asset import VisualAsset, ImageType
from app.services.intelligence.visual_intelligence_service import (
    process_visual_asset,
    process_document_visuals,
    get_visuals_for_topic,
)

router = APIRouter()


# ── GET /visuals/document/{doc_id} ────────────────────────────────────────────

@router.get("/document/{document_id}")
async def get_document_visuals(
    document_id: int,
    image_type: Optional[str] = None,
    only_processed: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Returns all visual assets extracted from a document."""
    query = select(VisualAsset).where(VisualAsset.document_id == document_id)

    if image_type:
        try:
            query = query.where(VisualAsset.image_type == ImageType(image_type))
        except ValueError:
            pass

    if only_processed:
        query = query.where(VisualAsset.ai_caption != None)

    query = query.order_by(VisualAsset.page_number, VisualAsset.image_index)
    result = await db.execute(query)
    visuals = result.scalars().all()

    return {
        "document_id": document_id,
        "total": len(visuals),
        "visuals": [_serialize(v) for v in visuals],
    }


# ── GET /visuals/topic/{topic_id} ─────────────────────────────────────────────

@router.get("/topic/{topic_id}")
async def get_topic_visuals(
    topic_id: int,
    image_type: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Returns all processed visual assets for a topic — ready for study."""
    img_type = None
    if image_type:
        try:
            img_type = ImageType(image_type)
        except ValueError:
            pass

    visuals = await get_visuals_for_topic(db, topic_id, img_type, limit)
    return {"topic_id": topic_id, "total": len(visuals), "visuals": visuals}


# ── GET /visuals/{visual_id} ──────────────────────────────────────────────────

@router.get("/{visual_id}")
async def get_visual(
    visual_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Returns full metadata for a single visual asset."""
    result = await db.execute(
        select(VisualAsset).where(VisualAsset.id == visual_id)
    )
    visual = result.scalar_one_or_none()
    if not visual:
        raise HTTPException(404, f"Visual {visual_id} not found")
    return _serialize(visual)


# ── GET /visuals/{visual_id}/image ────────────────────────────────────────────

@router.get("/{visual_id}/image")
async def serve_visual_image(
    visual_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Serves the raw image file for display in the frontend.

    Usage in frontend:
        <img src="/visuals/{visual_id}/image" />
    """
    result = await db.execute(
        select(VisualAsset).where(VisualAsset.id == visual_id)
    )
    visual = result.scalar_one_or_none()
    if not visual:
        raise HTTPException(404, f"Visual {visual_id} not found")

    image_path = Path(visual.image_path)
    if not image_path.exists():
        raise HTTPException(404, f"Image file not found: {visual.image_path}")

    return FileResponse(
        path=str(image_path),
        media_type="image/png",
        filename=image_path.name,
    )


# ── POST /visuals/{visual_id}/process ─────────────────────────────────────────

@router.post("/{visual_id}/process")
async def trigger_visual_processing(
    visual_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger AI captioning for a single visual asset.
    Useful for re-processing or processing missed visuals.
    """
    result = await db.execute(
        select(VisualAsset).where(VisualAsset.id == visual_id)
    )
    visual = result.scalar_one_or_none()
    if not visual:
        raise HTTPException(404, f"Visual {visual_id} not found")

    success = await process_visual_asset(db, visual_id)

    return {
        "visual_id": visual_id,
        "success":   success,
        "message":   "Processing complete" if success else "Processing failed — check logs",
    }


# ── POST /visuals/document/{doc_id}/process-all ───────────────────────────────

@router.post("/document/{document_id}/process-all")
async def process_all_document_visuals(
    document_id: int,
    background_tasks=None,
):
    """
    Triggers AI captioning for all unprocessed visuals in a document.
    Runs as a background task.
    """
    from fastapi import BackgroundTasks
    import asyncio

    async def run():
        await process_document_visuals(document_id)

    asyncio.create_task(run())

    return {
        "document_id": document_id,
        "message": f"Visual processing triggered for document {document_id}",
    }


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialize(v: VisualAsset) -> dict:
    return {
        "id":                  v.id,
        "document_id":         v.document_id,
        "page_number":         v.page_number,
        "image_index":         v.image_index,
        "image_url":           f"/api/visuals/{v.id}/image",
        "image_type":          v.image_type.value if v.image_type else "Other",
        "exam_use":            v.exam_use.value if v.exam_use else "Reference",
        "width_px":            v.width_px,
        "height_px":           v.height_px,
        "ocr_text":            v.ocr_text,
        "ai_caption":          v.ai_caption,
        "ai_summary":          v.ai_summary,
        "geo_entities":        v.geo_entities,
        "location_tags":       v.location_tags,
        "table_headers":       v.table_headers,
        "table_data_summary":  v.table_data_summary,
        "process_steps":       v.process_steps,
        "data_trend":          v.data_trend,
        "upsc_relevance_note": v.upsc_relevance_note,
        "probable_question":   v.probable_question,
        "topic_id":            v.topic_id,
        "subtopic_id":         v.subtopic_id,
        "is_captioned":        v.ai_caption is not None,
    }
