"""
services/intelligence/pyq_ingestion_service.py
────────────────────────────────────────────────
Ingests the PYQ JSON file (2016–2025 Mains questions + model answers)
into structured PYQ database records.

JSON format expected:
[
  {
    "year": 2023,
    "paper": "GS2",
    "question": "Discuss the role of Finance Commission...",
    "model_answer": "...",
    "marks": 15,
    "word_limit": 250
  },
  ...
]

Pipeline:
    1. Parse JSON
    2. For each question: auto-tag to taxonomy
    3. Detect command word
    4. Embed question text
    5. Store PYQ record
    6. Update MicroTag.pyq_weight based on frequency
"""

import json
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.models.pyq import PYQ, ExamType, GSSPaper, CommandWord, Difficulty
from app.models.topic import MicroTag
from app.models.document import Document
from app.services.tagging.auto_tagger import tag_chunk
from app.services.tagging.taxonomy_cache import ensure_loaded
from app.services.llm.embeddings import embed_many
from app.core.database import AsyncSessionFactory


# ── Command Word Detector ─────────────────────────────────────────────────────

_COMMAND_WORD_MAP = {
    "discuss":              CommandWord.DISCUSS,
    "analyze":              CommandWord.ANALYZE,
    "analyse":              CommandWord.ANALYZE,
    "examine":              CommandWord.EXAMINE,
    "evaluate":             CommandWord.EVALUATE,
    "comment":              CommandWord.COMMENT,
    "critically examine":   CommandWord.CRITICALLY,
    "critically analyze":   CommandWord.CRITICALLY,
    "critically analyse":   CommandWord.CRITICALLY,
    "explain":              CommandWord.EXPLAIN,
    "highlight":            CommandWord.HIGHLIGHT,
    "enumerate":            CommandWord.ENUMERATE,
}

def detect_command_word(question_text: str) -> CommandWord:
    q_lower = question_text.lower()
    for phrase, cw in _COMMAND_WORD_MAP.items():
        if phrase in q_lower:
            return cw
    return CommandWord.OTHER


def detect_paper_enum(paper_str: str) -> GSSPaper:
    mapping = {
        "GS1": GSSPaper.GS1, "GS-1": GSSPaper.GS1,
        "GS2": GSSPaper.GS2, "GS-2": GSSPaper.GS2,
        "GS3": GSSPaper.GS3, "GS-3": GSSPaper.GS3,
        "GS4": GSSPaper.GS4, "GS-4": GSSPaper.GS4,
        "ESSAY": GSSPaper.ESSAY, "Essay": GSSPaper.ESSAY,
    }
    return mapping.get(paper_str.strip().upper().replace(" ", ""), GSSPaper.GS1)


# ── JSON Parser ───────────────────────────────────────────────────────────────

def parse_pyq_json(raw_bytes: bytes) -> list[dict]:
    """
    Parses the PYQ JSON file into a list of question dicts.
    Handles both list format and nested dict format.
    """
    data = json.loads(raw_bytes)

    # Normalize to flat list
    if isinstance(data, list):
        return data

    # Handle nested format: {"GS1": [...], "GS2": [...]}
    flat = []
    if isinstance(data, dict):
        for paper_key, questions in data.items():
            if isinstance(questions, list):
                for q in questions:
                    if isinstance(q, dict):
                        q.setdefault("paper", paper_key)
                        flat.append(q)
    return flat


# ── Main Ingestion ────────────────────────────────────────────────────────────

async def ingest_pyq_json(
    document_id: int,
    file_bytes: bytes,
) -> dict:
    """
    Full PYQ JSON ingestion pipeline.

    Returns:
        {"total": N, "ingested": M, "failed": K}
    """
    async with AsyncSessionFactory() as db:
        # Ensure taxonomy loaded
        await ensure_loaded(db)

        # Parse
        try:
            questions = parse_pyq_json(file_bytes)
        except Exception as e:
            logger.error(f"PYQ JSON parse failed: {e}")
            return {"total": 0, "ingested": 0, "failed": 0}

        logger.info(f"📋 Ingesting {len(questions)} PYQ records...")

        ingested = failed = 0
        pyq_objects: list[PYQ] = []
        texts_to_embed: list[str] = []

        for q in questions:
            try:
                question_text = q.get("question") or q.get("question_text", "")
                if not question_text:
                    continue

                paper_str = q.get("paper", "GS1")
                year      = int(q.get("year", 2020))

                # Auto-tag
                tag = await tag_chunk(question_text)

                pyq = PYQ(
                    year=year,
                    exam_type=ExamType.MAINS,
                    paper=detect_paper_enum(paper_str),
                    question_text=question_text,
                    model_answer=q.get("model_answer") or q.get("answer", ""),
                    marks=q.get("marks"),
                    word_limit=q.get("word_limit"),
                    topic_id=tag.topic_id,
                    subtopic_id=tag.subtopic_id,
                    micro_tag_id=tag.micro_tag_id,
                    command_word=detect_command_word(question_text),
                    difficulty=Difficulty.MEDIUM,
                )
                db.add(pyq)
                pyq_objects.append(pyq)
                texts_to_embed.append(question_text)
                ingested += 1

            except Exception as e:
                logger.warning(f"PYQ entry failed: {e}")
                failed += 1

        await db.flush()   # get PYQ IDs

        # Embed all questions in batch
        if texts_to_embed:
            logger.info(f"🔢 Embedding {len(texts_to_embed)} PYQ questions...")
            embeddings = await embed_many(texts_to_embed)
            for pyq, emb in zip(pyq_objects, embeddings):
                pyq.embedding = emb

        await db.commit()

        # Update micro_tag PYQ weights based on frequency
        await _recalculate_pyq_weights(db)

        logger.info(f"✅ PYQ ingestion complete: {ingested} stored, {failed} failed")
        return {"total": len(questions), "ingested": ingested, "failed": failed}


# ── PYQ Weight Recalculator ───────────────────────────────────────────────────

async def _recalculate_pyq_weights(db: AsyncSession) -> None:
    """
    After ingesting PYQs, recalculates the pyq_weight of each micro_tag
    based on actual frequency in the PYQ database.

    This makes the system self-calibrating — as you add more PYQ data,
    the weights automatically reflect real exam patterns.
    """
    result = await db.execute(
        select(
            PYQ.micro_tag_id,
            func.count(PYQ.id).label("count"),
        )
        .where(PYQ.micro_tag_id != None)
        .group_by(PYQ.micro_tag_id)
    )
    freq_map = {row.micro_tag_id: row.count for row in result.fetchall()}

    if not freq_map:
        return

    max_freq = max(freq_map.values())

    for mt_id, count in freq_map.items():
        mt_result = await db.execute(
            select(MicroTag).where(MicroTag.id == mt_id)
        )
        mt = mt_result.scalar_one_or_none()
        if mt:
            # Normalize to 1–10 scale
            mt.pyq_weight = round(1.0 + (count / max_freq) * 9.0, 1)

    await db.commit()
    logger.info(f"✅ PYQ weights recalculated for {len(freq_map)} micro_tags")
