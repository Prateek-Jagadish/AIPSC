"""
services/ingestion/newspaper_pipeline.py
─────────────────────────────────────────
Dedicated pipeline for daily newspaper ingestion.

Different from normal PDF ingestion because:
    - We split by article, not by page
    - Each article is filtered for UPSC relevance
    - Relevant articles become CurrentAffair records (not just Chunks)
    - We generate probable question angles for each article
    - Date metadata is critical (when did this enter the knowledge base)

Pipeline:
    Newspaper PDF
        → extract full text (page by page)
        → split into articles (heuristic + LLM)
        → for each article: tag_newspaper_article()
        → if relevant: create CurrentAffair + embed summary
        → also create Chunk records for hybrid search
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from datetime import datetime, date
import re

from app.models.document import Document, Chunk, DocumentStatus
from app.models.current_affair import CurrentAffair, RelevanceLevel, ExamRelevance
from app.services.ingestion.pdf_processor import extract_pdf
from app.services.ingestion.chunker import chunk_page_text
from app.services.tagging.auto_tagger import tag_newspaper_article
from app.services.tagging.taxonomy_cache import ensure_loaded
from app.services.llm.embeddings import embed_many


# ── Article Splitter ──────────────────────────────────────────────────────────

def split_into_articles(full_text: str) -> list[str]:
    """
    Heuristic article splitter for newspaper text.

    Strategy:
        - Split on common newspaper article boundary patterns:
            * ALL CAPS headlines (≥4 words)
            * Lines starting with a date pattern
            * Double newlines followed by short capitalized line
        - Each segment must be at least 150 words to qualify

    Not perfect, but good enough to capture most articles.
    The LLM will further filter irrelevant ones.
    """
    # Split on double newlines (most PDFs have these between articles)
    raw_segments = re.split(r'\n{2,}', full_text)

    articles = []
    current_article = []
    current_word_count = 0

    for segment in raw_segments:
        seg = segment.strip()
        if not seg:
            continue

        words = seg.split()
        word_count = len(words)

        # Detect headline: short line, mostly uppercase or title-case
        is_headline = (
            word_count <= 15
            and word_count >= 3
            and (
                seg.isupper()
                or sum(1 for w in words if w[0].isupper()) / word_count > 0.6
            )
        )

        # If we hit a headline and have enough content, save the current article
        if is_headline and current_word_count >= 100:
            articles.append(" ".join(current_article))
            current_article = [seg]
            current_word_count = word_count
        else:
            current_article.append(seg)
            current_word_count += word_count

    # Flush last article
    if current_article and current_word_count >= 100:
        articles.append(" ".join(current_article))

    # Final fallback: if splitting failed, return whole text as one article
    if not articles:
        articles = [full_text]

    logger.info(f"📰 Split newspaper into {len(articles)} candidate articles")
    return articles


# ── Relevance Level Mapper ─────────────────────────────────────────────────────

def map_relevance_level(score: float) -> RelevanceLevel:
    if score >= 7.0:
        return RelevanceLevel.HIGH
    elif score >= 4.0:
        return RelevanceLevel.MEDIUM
    return RelevanceLevel.LOW


def map_exam_relevance(exam_str: str) -> ExamRelevance:
    mapping = {
        "Both":          ExamRelevance.BOTH,
        "Mains Only":    ExamRelevance.MAINS_ONLY,
        "Prelims Only":  ExamRelevance.PRELIMS_ONLY,
        "None":          ExamRelevance.NONE,
    }
    return mapping.get(exam_str, ExamRelevance.BOTH)


# ── Main Newspaper Pipeline ───────────────────────────────────────────────────

async def process_newspaper(
    db: AsyncSession,
    document_id: int,
) -> dict:
    """
    Full newspaper ingestion pipeline.

    Returns a summary dict:
    {
        "total_articles": int,
        "relevant_articles": int,
        "stored_ca_records": int,
    }
    """
    # Load document
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        logger.error(f"Document {document_id} not found")
        return {}

    publish_date = doc.publish_date.date() if doc.publish_date else date.today()
    publication  = doc.publication or "Unknown"

    logger.info(f"📰 Processing newspaper: {doc.title}")

    try:
        # ── Step 1: Extract full text ──────────────────────────────────────
        extraction = extract_pdf(doc.file_path)
        full_text  = "\n\n".join(p.text for p in extraction.pages if p.text)

        if not full_text.strip():
            logger.warning(f"No text extracted from newspaper {document_id}")
            return {}

        # ── Step 2: Ensure taxonomy loaded ────────────────────────────────
        await ensure_loaded(db)

        # ── Step 3: Split into candidate articles ─────────────────────────
        articles = split_into_articles(full_text)
        total_articles = len(articles)

        # ── Step 4: Tag + filter each article ─────────────────────────────
        relevant_summaries = []
        relevant_ca_objects = []

        for i, article_text in enumerate(articles):
            try:
                tag = await tag_newspaper_article(article_text)

                if not tag.is_upsc_relevant:
                    continue

                ca = CurrentAffair(
                    newspaper_date=publish_date,
                    publication=publication,
                    source_document_id=document_id,
                    headline=tag.headline,
                    raw_text=article_text[:3000],   # truncate very long articles
                    summary=tag.summary,
                    key_facts=tag.key_facts,
                    upsc_angle=tag.upsc_angle,
                    topic_id=tag.topic_id,
                    subtopic_id=tag.subtopic_id,
                    micro_tag_id=tag.micro_tag_id,
                    relevance_score=tag.relevance_score,
                    relevance_level=map_relevance_level(tag.relevance_score),
                    exam_relevance=map_exam_relevance(tag.exam_relevance),
                    probable_question=tag.probable_question,
                    mains_dimensions=tag.mains_dimensions,
                    prelims_facts=tag.prelims_facts,
                    static_linkage=tag.static_linkage,
                    has_map_reference=tag.has_map_reference,
                )
                db.add(ca)
                relevant_summaries.append(tag.summary)
                relevant_ca_objects.append(ca)

                logger.debug(f"  ✅ Relevant: {tag.headline[:60]}")

            except Exception as e:
                logger.warning(f"⚠️  Article {i} tagging failed: {e}")
                continue

        await db.flush()   # get CA IDs

        # ── Step 5: Embed all relevant summaries ──────────────────────────
        if relevant_summaries:
            embeddings = await embed_many(relevant_summaries)
            for ca, emb in zip(relevant_ca_objects, embeddings):
                ca.embedding = emb

        # ── Step 6: Update document status ────────────────────────────────
        doc.status       = DocumentStatus.EMBEDDED
        doc.processed_at = datetime.utcnow()
        doc.chunk_count  = len(relevant_ca_objects)

        await db.commit()

        summary = {
            "total_articles":    total_articles,
            "relevant_articles": len(relevant_ca_objects),
            "stored_ca_records": len(relevant_ca_objects),
        }

        logger.info(
            f"✅ Newspaper processed: "
            f"{total_articles} articles → "
            f"{len(relevant_ca_objects)} UPSC-relevant stored"
        )
        return summary

    except Exception as e:
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(e)
        await db.commit()
        logger.error(f"❌ Newspaper pipeline failed: {e}")
        return {}
