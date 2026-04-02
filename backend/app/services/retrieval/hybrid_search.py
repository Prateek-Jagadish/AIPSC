"""
services/retrieval/hybrid_search.py
─────────────────────────────────────
Hybrid retrieval engine: vector search + keyword search combined.

Why hybrid?
    Vector search alone  → good semantic match, misses exact terms
    Keyword search alone → misses paraphrased / related content
    Both together        → maximum recall for UPSC queries

Pipeline:
    1. Embed the user query (vector)
    2. Run pgvector similarity search across chunks, PYQs, CAs, visuals
    3. Run PostgreSQL full-text keyword search on same tables
    4. Merge + deduplicate results
    5. Score and rank by relevance
    6. Return top-N results with source type tagged

Used by: rag_pipeline.py (the answer generator)
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from sqlalchemy.orm import selectinload
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

from app.models.document import Chunk
from app.models.pyq import PYQ
from app.models.current_affair import CurrentAffair
from app.models.visual_asset import VisualAsset
from app.models.topic import Topic, Subtopic, MicroTag
from app.services.llm.embeddings import embed_text
from app.core.config import settings


# ── Result Types ──────────────────────────────────────────────────────────────

@dataclass
class RetrievedChunk:
    """A retrieved text chunk with its metadata."""
    source_type:    str        # "chunk" | "pyq" | "current_affair" | "visual"
    source_id:      int
    text:           str
    score:          float      # relevance score (higher = better)
    topic_name:     str = ""
    subtopic_name:  str = ""
    micro_tag_name: str = ""

    # Source-specific metadata
    year:           Optional[int]  = None   # for PYQs
    paper:          Optional[str]  = None   # for PYQs
    date:           Optional[str]  = None   # for current affairs
    headline:       Optional[str]  = None   # for current affairs
    image_path:     Optional[str]  = None   # for visuals
    image_type:     Optional[str]  = None   # for visuals


@dataclass
class HybridSearchResult:
    """Full result from the hybrid search engine."""
    query:          str
    topic_ids:      list[int] = field(default_factory=list)
    chunks:         list[RetrievedChunk] = field(default_factory=list)
    pyqs:           list[RetrievedChunk] = field(default_factory=list)
    current_affairs: list[RetrievedChunk] = field(default_factory=list)
    visuals:        list[RetrievedChunk] = field(default_factory=list)


# ── Query Tag Detector ────────────────────────────────────────────────────────

async def detect_query_tags(
    db: AsyncSession,
    query: str,
) -> dict:
    """
    Detects which topic/subtopic/micro_tag the query is about.
    Uses the taxonomy cache + simple keyword matching.

    Returns:
        {
            "topic_ids": [1, 2],
            "subtopic_ids": [5],
            "micro_tag_ids": [42, 43],
        }
    """
    from app.services.tagging.taxonomy_cache import (
        _cache,
        ensure_loaded,
    )
    await ensure_loaded(db)

    query_lower = query.lower()
    topic_ids, subtopic_ids, micro_tag_ids = set(), set(), set()

    # Match topic names
    for name, tid in _cache["topic_name_to_id"].items():
        if name.lower() in query_lower:
            topic_ids.add(tid)

    # Match subtopic names
    for name, sid in _cache["subtopic_name_to_id"].items():
        if name.lower() in query_lower:
            subtopic_ids.add(sid)

    # Match micro_tag names
    for name, mid in _cache["microtag_name_to_id"].items():
        if len(name) > 4 and name.lower() in query_lower:
            micro_tag_ids.add(mid)

    return {
        "topic_ids": list(topic_ids),
        "subtopic_ids": list(subtopic_ids),
        "micro_tag_ids": list(micro_tag_ids),
    }


# ── Vector Search ─────────────────────────────────────────────────────────────

async def vector_search_chunks(
    db: AsyncSession,
    query_embedding: list[float],
    topic_ids: list[int] = None,
    limit: int = None,
) -> list[RetrievedChunk]:
    """
    Semantic similarity search over text chunks using pgvector.
    Optionally filters by topic_ids for precision.
    """
    limit = limit or settings.VECTOR_SEARCH_LIMIT

    # Build pgvector cosine similarity query
    emb_str = f"[{','.join(str(x) for x in query_embedding)}]"

    if topic_ids:
        topic_filter = f"AND c.topic_id = ANY(ARRAY{topic_ids})"
    else:
        topic_filter = ""

    sql = text(f"""
        SELECT
            c.id,
            c.text,
            c.topic_id,
            c.subtopic_id,
            c.micro_tag_id,
            1 - (c.embedding <=> '{emb_str}'::vector) AS score,
            t.name AS topic_name,
            s.name AS subtopic_name,
            m.name AS micro_tag_name
        FROM chunks c
        LEFT JOIN topics    t ON t.id = c.topic_id
        LEFT JOIN subtopics s ON s.id = c.subtopic_id
        LEFT JOIN micro_tags m ON m.id = c.micro_tag_id
        WHERE c.embedding IS NOT NULL
        {topic_filter}
        ORDER BY c.embedding <=> '{emb_str}'::vector
        LIMIT :limit
    """)

    rows = (await db.execute(sql, {"limit": limit})).fetchall()

    return [
        RetrievedChunk(
            source_type="chunk",
            source_id=r.id,
            text=r.text,
            score=float(r.score),
            topic_name=r.topic_name or "",
            subtopic_name=r.subtopic_name or "",
            micro_tag_name=r.micro_tag_name or "",
        )
        for r in rows
    ]


async def vector_search_pyqs(
    db: AsyncSession,
    query_embedding: list[float],
    topic_ids: list[int] = None,
    limit: int = None,
) -> list[RetrievedChunk]:
    """Semantic search over PYQ question text."""
    limit = limit or settings.VECTOR_SEARCH_LIMIT
    emb_str = f"[{','.join(str(x) for x in query_embedding)}]"

    topic_filter = f"AND p.topic_id = ANY(ARRAY{topic_ids})" if topic_ids else ""

    sql = text(f"""
        SELECT
            p.id,
            p.question_text AS text,
            p.year,
            p.paper,
            p.model_answer,
            p.topic_id,
            1 - (p.embedding <=> '{emb_str}'::vector) AS score,
            t.name AS topic_name,
            s.name AS subtopic_name,
            m.name AS micro_tag_name
        FROM pyqs p
        LEFT JOIN topics    t ON t.id = p.topic_id
        LEFT JOIN subtopics s ON s.id = p.subtopic_id
        LEFT JOIN micro_tags m ON m.id = p.micro_tag_id
        WHERE p.embedding IS NOT NULL
        {topic_filter}
        ORDER BY p.embedding <=> '{emb_str}'::vector
        LIMIT :limit
    """)

    rows = (await db.execute(sql, {"limit": limit})).fetchall()

    return [
        RetrievedChunk(
            source_type="pyq",
            source_id=r.id,
            text=r.text,
            score=float(r.score),
            topic_name=r.topic_name or "",
            subtopic_name=r.subtopic_name or "",
            micro_tag_name=r.micro_tag_name or "",
            year=r.year,
            paper=str(r.paper) if r.paper else None,
        )
        for r in rows
    ]


async def vector_search_current_affairs(
    db: AsyncSession,
    query_embedding: list[float],
    topic_ids: list[int] = None,
    limit: int = None,
) -> list[RetrievedChunk]:
    """Semantic search over current affairs summaries."""
    limit = limit or settings.VECTOR_SEARCH_LIMIT
    emb_str = f"[{','.join(str(x) for x in query_embedding)}]"

    topic_filter = f"AND ca.topic_id = ANY(ARRAY{topic_ids})" if topic_ids else ""

    sql = text(f"""
        SELECT
            ca.id,
            ca.summary AS text,
            ca.headline,
            ca.newspaper_date,
            ca.probable_question,
            ca.mains_dimensions,
            1 - (ca.embedding <=> '{emb_str}'::vector) AS score,
            t.name AS topic_name
        FROM current_affairs ca
        LEFT JOIN topics t ON t.id = ca.topic_id
        WHERE ca.embedding IS NOT NULL
        {topic_filter}
        ORDER BY ca.embedding <=> '{emb_str}'::vector
        LIMIT :limit
    """)

    rows = (await db.execute(sql, {"limit": limit})).fetchall()

    return [
        RetrievedChunk(
            source_type="current_affair",
            source_id=r.id,
            text=r.text,
            score=float(r.score),
            topic_name=r.topic_name or "",
            headline=r.headline,
            date=str(r.newspaper_date) if r.newspaper_date else None,
        )
        for r in rows
    ]


async def vector_search_visuals(
    db: AsyncSession,
    query_embedding: list[float],
    topic_ids: list[int] = None,
    limit: int = 5,
) -> list[RetrievedChunk]:
    """Semantic search over visual asset AI captions."""
    emb_str = f"[{','.join(str(x) for x in query_embedding)}]"

    topic_filter = f"AND v.topic_id = ANY(ARRAY{topic_ids})" if topic_ids else ""

    sql = text(f"""
        SELECT
            v.id,
            v.ai_caption AS text,
            v.ai_summary,
            v.image_path,
            v.image_type,
            1 - (v.embedding <=> '{emb_str}'::vector) AS score,
            t.name AS topic_name
        FROM visual_assets v
        LEFT JOIN topics t ON t.id = v.topic_id
        WHERE v.embedding IS NOT NULL
        {topic_filter}
        ORDER BY v.embedding <=> '{emb_str}'::vector
        LIMIT :limit
    """)

    rows = (await db.execute(sql, {"limit": limit})).fetchall()

    return [
        RetrievedChunk(
            source_type="visual",
            source_id=r.id,
            text=r.text or r.ai_summary or "",
            score=float(r.score),
            topic_name=r.topic_name or "",
            image_path=r.image_path,
            image_type=str(r.image_type) if r.image_type else None,
        )
        for r in rows
        if r.text  # only include visuals that have been captioned
    ]


# ── Keyword Search ────────────────────────────────────────────────────────────

async def keyword_search_chunks(
    db: AsyncSession,
    query: str,
    limit: int = None,
) -> list[RetrievedChunk]:
    """
    Full-text keyword search over chunks using PostgreSQL to_tsquery.
    Handles multi-word queries by converting to tsquery format.
    """
    limit = limit or settings.KEYWORD_SEARCH_LIMIT

    # Convert query to tsquery: "demand supply" → "demand & supply"
    words = [w for w in query.strip().split() if len(w) > 2]
    if not words:
        return []
    tsquery = " & ".join(words)

    sql = text("""
        SELECT
            c.id,
            c.text,
            c.topic_id,
            t.name AS topic_name,
            s.name AS subtopic_name,
            ts_rank(to_tsvector('english', c.text), to_tsquery('english', :tsquery)) AS score
        FROM chunks c
        LEFT JOIN topics    t ON t.id = c.topic_id
        LEFT JOIN subtopics s ON s.id = c.subtopic_id
        WHERE to_tsvector('english', c.text) @@ to_tsquery('english', :tsquery)
        ORDER BY score DESC
        LIMIT :limit
    """)

    try:
        rows = (await db.execute(sql, {"tsquery": tsquery, "limit": limit})).fetchall()
    except Exception as e:
        logger.warning(f"Keyword search failed (tsquery syntax): {e}")
        return []

    return [
        RetrievedChunk(
            source_type="chunk",
            source_id=r.id,
            text=r.text,
            score=float(r.score) * 0.7,  # scale down vs vector scores
            topic_name=r.topic_name or "",
            subtopic_name=r.subtopic_name or "",
        )
        for r in rows
    ]


# ── Merge + Deduplicate ───────────────────────────────────────────────────────

def merge_results(
    vector_results: list[RetrievedChunk],
    keyword_results: list[RetrievedChunk],
    final_limit: int = None,
) -> list[RetrievedChunk]:
    """
    Merges vector and keyword results:
        - Deduplicates by (source_type, source_id)
        - If same item appears in both, takes the higher score
        - Sorts by score descending
        - Returns top final_limit items
    """
    final_limit = final_limit or settings.FINAL_CONTEXT_LIMIT * 2

    seen: dict[tuple, RetrievedChunk] = {}

    for item in vector_results + keyword_results:
        key = (item.source_type, item.source_id)
        if key not in seen or item.score > seen[key].score:
            seen[key] = item

    ranked = sorted(seen.values(), key=lambda x: x.score, reverse=True)
    return ranked[:final_limit]


# ── Main Hybrid Search ────────────────────────────────────────────────────────

async def hybrid_search(
    db: AsyncSession,
    query: str,
    include_pyqs: bool = True,
    include_ca: bool = True,
    include_visuals: bool = True,
    topic_filter_ids: list[int] = None,
) -> HybridSearchResult:
    """
    Main entry point for retrieval.

    Steps:
        1. Embed the query
        2. Detect topic tags from query text
        3. Vector search across all relevant tables
        4. Keyword search on chunks
        5. Merge and rank everything
        6. Return structured HybridSearchResult

    Args:
        query:             the user's question
        include_pyqs:      include PYQ search
        include_ca:        include current affairs search
        include_visuals:   include visual assets search
        topic_filter_ids:  restrict search to specific topics (optional)
    """
    logger.info(f"🔍 Hybrid search: '{query[:80]}'")

    # Step 1: Embed query
    query_embedding = await embed_text(query)

    # Step 2: Detect topic tags
    detected_tags = await detect_query_tags(db, query)
    topic_ids = topic_filter_ids or detected_tags["topic_ids"] or None

    logger.debug(f"  Detected topics: {topic_ids}")

    # Step 3: Vector search all tables in parallel conceptually
    # (run sequentially to avoid DB overload — fast enough for our scale)
    chunk_vec   = await vector_search_chunks(db, query_embedding, topic_ids)
    chunk_kw    = await keyword_search_chunks(db, query)
    all_chunks  = merge_results(chunk_vec, chunk_kw, final_limit=settings.FINAL_CONTEXT_LIMIT)

    pyq_results = []
    if include_pyqs:
        pyq_results = await vector_search_pyqs(db, query_embedding, topic_ids)
        pyq_results = pyq_results[:settings.FINAL_CONTEXT_LIMIT]

    ca_results = []
    if include_ca:
        ca_results = await vector_search_current_affairs(db, query_embedding, topic_ids)
        ca_results = ca_results[:settings.FINAL_CONTEXT_LIMIT]

    visual_results = []
    if include_visuals:
        visual_results = await vector_search_visuals(db, query_embedding, topic_ids)

    result = HybridSearchResult(
        query=query,
        topic_ids=topic_ids or [],
        chunks=all_chunks,
        pyqs=pyq_results,
        current_affairs=ca_results,
        visuals=visual_results,
    )

    logger.info(
        f"✅ Retrieved: {len(all_chunks)} chunks | "
        f"{len(pyq_results)} PYQs | "
        f"{len(ca_results)} CAs | "
        f"{len(visual_results)} visuals"
    )

    return result
