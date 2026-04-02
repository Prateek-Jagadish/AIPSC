"""
services/intelligence/visual_intelligence_service.py
──────────────────────────────────────────────────────
AI-powered visual understanding pipeline.

Every image extracted from a PDF goes through this service:
    1. Classify the image type (Map / Table / Graph / Diagram / Photo)
    2. Generate a UPSC-focused AI caption using GPT-4o Vision
    3. Extract structured metadata (geo_entities, table headers, process steps)
    4. Generate embedding from the AI caption
    5. Store everything back to the VisualAsset record

Why this matters:
    Without this, images are just binary blobs.
    After this, a map of Protected Areas becomes retrievable when
    you ask "What biodiversity hotspots should I revise?"

GPT-4o Vision is used here — it receives the actual image bytes
and generates captions that understand visual content, not just text.
"""

import base64
import io
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.models.visual_asset import VisualAsset, ImageType, ExamUse
from app.models.document import Document
from app.services.llm.embeddings import embed_text
from app.services.llm.prompts import image_caption_prompt
from app.services.llm.llm_client import _parse_json

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


# ── Image Type Classifier ─────────────────────────────────────────────────────

async def classify_image_with_vision(
    image_bytes: bytes,
    surrounding_text: str = "",
) -> ImageType:
    """
    Uses GPT-4o Vision to classify image type.
    More accurate than the heuristic in document_ingestion_service.py.
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = await _client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            max_tokens=50,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "low",
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Classify this image as exactly one of: "
                                "Map, Table, Graph, Diagram, Flowchart, Photo, Infographic, Other. "
                                "Reply with only the single word."
                            ),
                        },
                    ],
                }
            ],
        )
        label = response.choices[0].message.content.strip().title()
        try:
            return ImageType(label)
        except ValueError:
            return ImageType.OTHER

    except Exception as e:
        logger.warning(f"Vision classification failed: {e}")
        return ImageType.OTHER


# ── Caption Generator ─────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def generate_ai_caption(
    image_bytes: bytes,
    image_type: ImageType,
    topic_name: str,
    ocr_text: str = "",
    surrounding_text: str = "",
) -> dict:
    """
    Generates a comprehensive UPSC-focused AI caption for an image.

    Uses GPT-4o Vision with:
        - The actual image (so it can see the content visually)
        - Context from OCR text inside the image
        - Context from surrounding page text
        - Topic context for UPSC relevance

    Returns a structured dict with:
        - ai_caption, ai_summary
        - geo_entities, location_tags (for maps)
        - table_headers, table_data_summary (for tables)
        - process_steps, data_trend (for diagrams/graphs)
        - upsc_relevance_note, probable_question
        - exam_use
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Build the text prompt
    text_prompt = image_caption_prompt(
        image_type=image_type.value,
        ocr_text=ocr_text,
        surrounding_text=surrounding_text,
        topic_name=topic_name,
    )

    try:
        response = await _client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            max_tokens=1000,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": "You are a UPSC expert analyzing visual study material. Always respond with valid JSON only.",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "text",
                            "text": text_prompt,
                        },
                    ],
                },
            ],
        )

        raw = response.choices[0].message.content or "{}"
        return _parse_json(raw)

    except Exception as e:
        logger.error(f"Caption generation failed: {e}")
        return {
            "ai_caption": f"Image from {topic_name} study material.",
            "ai_summary": f"{image_type.value} related to {topic_name}.",
            "exam_use":   "Reference",
            "upsc_relevance_note": "",
            "probable_question": "",
        }


# ── Exam Use Mapper ───────────────────────────────────────────────────────────

def map_exam_use(exam_use_str: str) -> ExamUse:
    mapping = {
        "Mains Diagram":    ExamUse.MAINS_DIAGRAM,
        "Prelims Revision": ExamUse.PRELIMS_REVISION,
        "Both":             ExamUse.BOTH,
        "Reference":        ExamUse.REFERENCE,
    }
    return mapping.get(exam_use_str, ExamUse.REFERENCE)


# ── Single Visual Processor ───────────────────────────────────────────────────

async def process_visual_asset(
    db: AsyncSession,
    visual_id: int,
) -> bool:
    """
    Processes one VisualAsset:
        1. Load from DB
        2. Read image bytes from disk
        3. Classify image type (Vision)
        4. Generate AI caption (Vision)
        5. Embed the caption
        6. Save everything back to DB

    Returns True on success.
    """
    result = await db.execute(
        select(VisualAsset).where(VisualAsset.id == visual_id)
    )
    visual = result.scalar_one_or_none()
    if not visual:
        logger.error(f"VisualAsset {visual_id} not found")
        return False

    # Read image bytes from disk
    image_path = Path(visual.image_path)
    if not image_path.exists():
        logger.error(f"Image file not found: {image_path}")
        return False

    image_bytes = image_path.read_bytes()

    # Get topic name for context
    topic_name = "UPSC Study Material"
    if visual.topic:
        topic_name = visual.topic.name
    elif visual.subtopic:
        topic_name = visual.subtopic.name

    try:
        # Step 1: Classify image type with Vision
        classified_type = await classify_image_with_vision(
            image_bytes=image_bytes,
            surrounding_text=visual.surrounding_text or "",
        )
        visual.image_type = classified_type
        logger.debug(f"  Image {visual_id} classified as: {classified_type.value}")

        # Step 2: Generate AI caption with Vision
        caption_data = await generate_ai_caption(
            image_bytes=image_bytes,
            image_type=classified_type,
            topic_name=topic_name,
            ocr_text=visual.ocr_text or "",
            surrounding_text=visual.surrounding_text or "",
        )

        # Step 3: Populate VisualAsset fields
        visual.ai_caption    = caption_data.get("ai_caption", "")
        visual.ai_summary    = caption_data.get("ai_summary", "")
        visual.exam_use      = map_exam_use(caption_data.get("exam_use", "Reference"))
        visual.upsc_relevance_note = caption_data.get("upsc_relevance_note", "")
        visual.probable_question   = caption_data.get("probable_question", "")

        # Type-specific fields
        visual.geo_entities       = caption_data.get("geo_entities", "")
        visual.location_tags      = caption_data.get("location_tags", "")
        visual.table_headers      = caption_data.get("table_headers", "")
        visual.table_data_summary = caption_data.get("table_data_summary", "")
        visual.process_steps      = caption_data.get("process_steps", "")
        visual.data_trend         = caption_data.get("data_trend", "")

        # Step 4: Embed the caption
        embed_text_content = (
            f"{visual.ai_caption} {visual.geo_entities or ''} "
            f"{visual.table_data_summary or ''} {visual.process_steps or ''}"
        ).strip()

        if embed_text_content:
            visual.embedding = await embed_text(embed_text_content)

        await db.commit()
        logger.info(
            f"✅ Visual {visual_id} processed: "
            f"{classified_type.value} | {topic_name}"
        )
        return True

    except Exception as e:
        logger.error(f"❌ Visual processing failed for {visual_id}: {e}")
        return False


# ── Batch Document Visual Processor ──────────────────────────────────────────

async def process_document_visuals(document_id: int) -> dict:
    """
    Processes all visual assets for a document.
    Called after document ingestion completes.

    Returns summary: {"total": N, "processed": M, "failed": K}
    """
    async with AsyncSessionFactory() as db:
        result = await db.execute(
            select(VisualAsset)
            .where(VisualAsset.document_id == document_id)
            .where(VisualAsset.ai_caption == None)  # only unprocessed
        )
        visuals = result.scalars().all()

        if not visuals:
            logger.info(f"No unprocessed visuals for document {document_id}")
            return {"total": 0, "processed": 0, "failed": 0}

        logger.info(
            f"🖼️  Processing {len(visuals)} visuals "
            f"for document {document_id}..."
        )

        processed = failed = 0

        for visual in visuals:
            # Re-open session per visual to avoid long transactions
            async with AsyncSessionFactory() as vis_db:
                success = await process_visual_asset(vis_db, visual.id)
                if success:
                    processed += 1
                else:
                    failed += 1

        summary = {
            "total":     len(visuals),
            "processed": processed,
            "failed":    failed,
        }

        logger.info(
            f"✅ Document {document_id} visuals done: "
            f"{processed} processed, {failed} failed"
        )
        return summary


# ── Retrieve Visuals for Display ──────────────────────────────────────────────

async def get_visuals_for_topic(
    db: AsyncSession,
    topic_id: int,
    image_type: ImageType = None,
    limit: int = 10,
) -> list[dict]:
    """
    Retrieves processed visual assets for a topic, ready for display.

    Returns a list of dicts with:
        - image_path (to serve the file)
        - image_type
        - ai_caption, ai_summary
        - exam_use
        - upsc_relevance_note
        - probable_question
        - geo_entities (for maps)
    """
    query = (
        select(VisualAsset)
        .where(VisualAsset.topic_id == topic_id)
        .where(VisualAsset.ai_caption != None)
    )

    if image_type:
        query = query.where(VisualAsset.image_type == image_type)

    query = query.limit(limit)
    result = await db.execute(query)
    visuals = result.scalars().all()

    return [
        {
            "id":                  v.id,
            "image_path":          v.image_path,
            "image_type":          v.image_type.value if v.image_type else "Other",
            "ai_summary":          v.ai_summary,
            "ai_caption":          v.ai_caption,
            "exam_use":            v.exam_use.value if v.exam_use else "Reference",
            "upsc_relevance_note": v.upsc_relevance_note,
            "probable_question":   v.probable_question,
            "geo_entities":        v.geo_entities,
            "location_tags":       v.location_tags,
            "table_headers":       v.table_headers,
            "table_data_summary":  v.table_data_summary,
            "process_steps":       v.process_steps,
            "data_trend":          v.data_trend,
            "width_px":            v.width_px,
            "height_px":           v.height_px,
        }
        for v in visuals
    ]
