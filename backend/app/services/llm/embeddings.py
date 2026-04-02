"""
services/llm/embeddings.py
───────────────────────────
Handles all vector embedding generation using OpenAI's
text-embedding-3-large model.

Used by:
    - Tagging service    (embed chunks after tagging)
    - Visual service     (embed AI captions of images)
    - Current affairs    (embed article summaries)
    - PYQ service        (embed question text)
    - Query pipeline     (embed user queries at retrieval time)

Design:
    - Batch embedding to minimize API calls
    - Retry on rate limit / transient errors
    - Returns numpy-compatible float lists for pgvector storage
"""

from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from loguru import logger
import asyncio

from app.core.config import settings


# ── Client ────────────────────────────────────────────────────────────────────

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

EMBEDDING_MODEL = settings.OPENAI_EMBEDDING_MODEL   # text-embedding-3-large
EMBEDDING_DIM   = 3072                               # output dimension for 3-large
BATCH_SIZE      = 100                                # max texts per API call


# ── Single Embedding ──────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def embed_text(text: str) -> list[float]:
    """
    Generate a single embedding vector for a text string.
    Returns a list of 3072 floats.
    """
    text = text.strip().replace("\n", " ")
    if not text:
        return [0.0] * EMBEDDING_DIM

    response = await _client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


# ── Batch Embedding ───────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts in one API call.
    More efficient than calling embed_text() in a loop.

    Returns a list of embedding vectors (same order as input).
    """
    # Clean inputs
    cleaned = [t.strip().replace("\n", " ") or " " for t in texts]

    response = await _client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=cleaned,
    )

    # API returns results in order — sort by index just to be safe
    sorted_data = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_data]


# ── Large-scale Batch (auto-splits) ──────────────────────────────────────────

async def embed_many(texts: list[str]) -> list[list[float]]:
    """
    Embed an arbitrary number of texts.
    Automatically splits into batches of BATCH_SIZE.
    Adds a small delay between batches to avoid rate limits.

    Returns embeddings in the same order as input.
    """
    if not texts:
        return []

    all_embeddings = []
    batches = [texts[i:i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]

    logger.info(f"🔢 Embedding {len(texts)} texts in {len(batches)} batches...")

    for i, batch in enumerate(batches):
        try:
            batch_embeddings = await embed_batch(batch)
            all_embeddings.extend(batch_embeddings)
            logger.debug(f"  Batch {i+1}/{len(batches)} embedded ({len(batch)} texts)")

            # Small delay between batches to respect rate limits
            if i < len(batches) - 1:
                await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"❌ Embedding batch {i+1} failed: {e}")
            # Fill with zero vectors for failed batch to preserve ordering
            all_embeddings.extend([[0.0] * EMBEDDING_DIM] * len(batch))

    logger.info(f"✅ Embedded {len(all_embeddings)} texts")
    return all_embeddings
