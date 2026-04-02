"""
services/tagging/auto_tagger.py
────────────────────────────────
The auto-tagging engine.

Takes a raw text chunk and returns:
    - topic_id
    - subtopic_id
    - micro_tag_id
    - confidence score
    - whether it's UPSC relevant at all

How it works:
    1. Gets the full taxonomy tree as a JSON string (from cache)
    2. Sends chunk + taxonomy to GPT-4o with a structured prompt
    3. Parses the JSON response
    4. Resolves name strings → DB IDs via the taxonomy cache
    5. Returns a TagResult

Used by:
    - Chunk tagging service (after PDF ingestion)
    - Newspaper article tagger
    - PYQ tagger
"""

from dataclasses import dataclass
from typing import Optional
from loguru import logger

from app.services.llm.llm_client import call_llm_json
from app.services.llm.prompts import auto_tag_chunk_prompt, tag_newspaper_article_prompt
from app.services.tagging.taxonomy_cache import get_taxonomy_context, resolve_tag_ids


# ── Result Types ──────────────────────────────────────────────────────────────

@dataclass
class TagResult:
    """Result of tagging a single text chunk."""
    is_upsc_relevant: bool
    topic_id:         Optional[int]
    subtopic_id:      Optional[int]
    micro_tag_id:     Optional[int]
    confidence:       float
    reasoning:        str = ""


@dataclass
class NewspaperTagResult:
    """Result of tagging a newspaper article."""
    is_upsc_relevant:    bool
    headline:            str = ""
    summary:             str = ""
    key_facts:           str = ""
    upsc_angle:          str = ""
    topic_id:            Optional[int] = None
    subtopic_id:         Optional[int] = None
    micro_tag_id:        Optional[int] = None
    relevance_score:     float = 5.0
    exam_relevance:      str = "Both"
    probable_question:   str = ""
    mains_dimensions:    str = ""
    prelims_facts:       str = ""
    static_linkage:      str = ""
    has_map_reference:   bool = False


# ── Chunk Tagger ──────────────────────────────────────────────────────────────

async def tag_chunk(chunk_text: str) -> TagResult:
    """
    Tags a single text chunk against the UPSC taxonomy.

    Args:
        chunk_text: the raw text to classify

    Returns:
        TagResult with topic/subtopic/microtag IDs + confidence
    """
    taxonomy_context = get_taxonomy_context()

    if not taxonomy_context:
        logger.warning("⚠️  Taxonomy not loaded — returning untagged result")
        return TagResult(is_upsc_relevant=False, topic_id=None,
                         subtopic_id=None, micro_tag_id=None, confidence=0.0)

    # Build and call prompt
    prompt = auto_tag_chunk_prompt(chunk_text, taxonomy_context)
    result = await call_llm_json(prompt)

    if not result:
        return TagResult(is_upsc_relevant=False, topic_id=None,
                         subtopic_id=None, micro_tag_id=None, confidence=0.0,
                         reasoning="LLM returned empty result")

    is_relevant = result.get("is_upsc_relevant", True)

    if not is_relevant:
        return TagResult(is_upsc_relevant=False, topic_id=None,
                         subtopic_id=None, micro_tag_id=None, confidence=0.0,
                         reasoning="Not UPSC relevant")

    # Resolve names → DB IDs
    ids = resolve_tag_ids(
        topic_name=result.get("topic_name"),
        subtopic_name=result.get("subtopic_name"),
        microtag_name=result.get("micro_tag_name"),
    )

    return TagResult(
        is_upsc_relevant=True,
        topic_id=ids["topic_id"],
        subtopic_id=ids["subtopic_id"],
        micro_tag_id=ids["micro_tag_id"],
        confidence=float(result.get("confidence", 0.7)),
        reasoning=result.get("reasoning", ""),
    )


# ── Batch Chunk Tagger ────────────────────────────────────────────────────────

async def tag_chunks_batch(chunk_texts: list[str]) -> list[TagResult]:
    """
    Tags a list of chunks sequentially.
    Each call is async but we await each one in order
    to avoid overwhelming the OpenAI API.

    For production scale, this can be parallelised with semaphore limiting.
    """
    results = []
    total = len(chunk_texts)

    for i, text in enumerate(chunk_texts):
        try:
            tag = await tag_chunk(text)
            results.append(tag)

            if (i + 1) % 10 == 0:
                logger.info(f"  🏷️  Tagged {i+1}/{total} chunks")

        except Exception as e:
            logger.error(f"❌ Tagging failed for chunk {i}: {e}")
            results.append(TagResult(
                is_upsc_relevant=False,
                topic_id=None, subtopic_id=None, micro_tag_id=None,
                confidence=0.0, reasoning=f"Error: {e}"
            ))

    logger.info(f"✅ Batch tagging complete: {total} chunks processed")
    return results


# ── Newspaper Article Tagger ──────────────────────────────────────────────────

async def tag_newspaper_article(article_text: str) -> NewspaperTagResult:
    """
    Tags a single newspaper article:
        - Filters UPSC relevance
        - Summarizes
        - Maps to taxonomy
        - Generates probable question angle

    Returns a NewspaperTagResult ready to store as CurrentAffair.
    """
    taxonomy_context = get_taxonomy_context()
    prompt  = tag_newspaper_article_prompt(article_text, taxonomy_context)
    result  = await call_llm_json(prompt)

    if not result or not result.get("is_upsc_relevant", False):
        return NewspaperTagResult(is_upsc_relevant=False)

    # Resolve taxonomy names → IDs
    ids = resolve_tag_ids(
        topic_name=result.get("topic_name"),
        subtopic_name=result.get("subtopic_name"),
        microtag_name=result.get("micro_tag_name"),
    )

    return NewspaperTagResult(
        is_upsc_relevant=True,
        headline=result.get("headline", ""),
        summary=result.get("summary", ""),
        key_facts=result.get("key_facts", ""),
        upsc_angle=result.get("upsc_angle", ""),
        topic_id=ids["topic_id"],
        subtopic_id=ids["subtopic_id"],
        micro_tag_id=ids["micro_tag_id"],
        relevance_score=float(result.get("relevance_score", 5.0)),
        exam_relevance=result.get("exam_relevance", "Both"),
        probable_question=result.get("probable_question", ""),
        mains_dimensions=result.get("mains_dimensions", ""),
        prelims_facts=result.get("prelims_facts", ""),
        static_linkage=result.get("static_linkage", ""),
        has_map_reference=bool(result.get("has_map_reference", False)),
    )
