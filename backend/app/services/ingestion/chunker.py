"""
services/ingestion/chunker.py
──────────────────────────────
Splits extracted page text into overlapping token-limited chunks for RAG.

Strategy:
    - Clean text → split into sentences → fill a sliding token window
    - Respect CHUNK_SIZE and CHUNK_OVERLAP from settings
    - Preserve page number per chunk for metadata

Why overlap matters:
    If a concept spans a chunk boundary, overlap ensures retrieval
    always captures the full context.
"""

import re
import tiktoken
from dataclasses import dataclass, field
from loguru import logger

from app.core.config import settings


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class TextChunk:
    """One chunk of text ready for tagging, embedding, and storage."""
    text:        str
    page_number: int
    chunk_index: int      # document-wide sequence number
    token_count: int


# ── Tokenizer ─────────────────────────────────────────────────────────────────

# cl100k_base is compatible with text-embedding-3-large and GPT-4o
_TOKENIZER = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(_TOKENIZER.encode(text))


# ── Utilities ─────────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Light cleaning — collapse extra whitespace, preserve paragraphs."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    return text.strip()


def split_into_sentences(text: str) -> list:
    """Split text into sentence units on punctuation boundaries."""
    parts = re.split(r'(?<=[.?!])\s+', text)
    return [p.strip() for p in parts if p.strip()]


# ── Core Chunker ──────────────────────────────────────────────────────────────

def chunk_page_text(
    text: str,
    page_number: int,
    start_chunk_index: int = 0,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> list:
    """
    Splits one page's text into overlapping token-limited TextChunks.

    Algorithm:
        1. Clean and sentence-tokenize the text
        2. Greedily fill a window up to chunk_size tokens
        3. When full: save chunk, slide back by chunk_overlap tokens
        4. Repeat until all sentences are consumed
    """
    _size    = chunk_size    or settings.CHUNK_SIZE
    _overlap = chunk_overlap or settings.CHUNK_OVERLAP

    text = clean_text(text)
    if not text:
        return []

    sentences   = split_into_sentences(text)
    chunks      = []
    chunk_index = start_chunk_index

    current_sentences = []
    current_tokens    = 0

    for sentence in sentences:
        s_tokens = count_tokens(sentence)

        # Force-split sentences that alone exceed chunk_size
        if s_tokens > _size:
            if current_sentences:
                chunk_text = " ".join(current_sentences)
                chunks.append(TextChunk(
                    text=chunk_text,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    token_count=count_tokens(chunk_text),
                ))
                chunk_index += 1
                current_sentences, current_tokens = [], 0

            words, word_buf, word_tok = sentence.split(), [], 0
            for word in words:
                wt = count_tokens(word)
                if word_tok + wt > _size and word_buf:
                    chunk_text = " ".join(word_buf)
                    chunks.append(TextChunk(
                        text=chunk_text,
                        page_number=page_number,
                        chunk_index=chunk_index,
                        token_count=count_tokens(chunk_text),
                    ))
                    chunk_index += 1
                    word_buf, word_tok = [], 0
                word_buf.append(word)
                word_tok += wt
            if word_buf:
                chunk_text = " ".join(word_buf)
                chunks.append(TextChunk(
                    text=chunk_text,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    token_count=count_tokens(chunk_text),
                ))
                chunk_index += 1
            continue

        # Window full → save and slide back by overlap
        if current_tokens + s_tokens > _size:
            if current_sentences:
                chunk_text = " ".join(current_sentences)
                chunks.append(TextChunk(
                    text=chunk_text,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    token_count=count_tokens(chunk_text),
                ))
                chunk_index += 1

                # Keep tail sentences that fit inside overlap window
                overlap_buf, overlap_tok = [], 0
                for s in reversed(current_sentences):
                    st = count_tokens(s)
                    if overlap_tok + st <= _overlap:
                        overlap_buf.insert(0, s)
                        overlap_tok += st
                    else:
                        break
                current_sentences, current_tokens = overlap_buf, overlap_tok

        current_sentences.append(sentence)
        current_tokens += s_tokens

    # Flush remaining sentences
    if current_sentences:
        chunk_text = " ".join(current_sentences)
        chunks.append(TextChunk(
            text=chunk_text,
            page_number=page_number,
            chunk_index=chunk_index,
            token_count=count_tokens(chunk_text),
        ))

    return chunks


# ── Document-level Entry Point ────────────────────────────────────────────────

def chunk_document_pages(pages: list) -> list:
    """
    Chunks all pages of a document into a flat ordered list of TextChunks.

    Args:
        pages: list of PageData from pdf_processor.py

    Returns:
        Flat list of TextChunks across the entire document.
    """
    all_chunks   = []
    global_index = 0

    for page in pages:
        if not page.text:
            continue
        page_chunks = chunk_page_text(
            text=page.text,
            page_number=page.page_number,
            start_chunk_index=global_index,
        )
        all_chunks.extend(page_chunks)
        global_index += len(page_chunks)

    avg_tokens = (
        sum(c.token_count for c in all_chunks) // len(all_chunks)
        if all_chunks else 0
    )
    logger.info(
        f"✂️  {len(pages)} pages → {len(all_chunks)} chunks "
        f"(avg {avg_tokens} tokens/chunk)"
    )
    return all_chunks
