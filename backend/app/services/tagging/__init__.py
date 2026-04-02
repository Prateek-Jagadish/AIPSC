"""services/tagging — Auto-tagging pipeline."""
from app.services.tagging.auto_tagger import tag_chunk, tag_chunks_batch, tag_newspaper_article
from app.services.tagging.taxonomy_cache import load_taxonomy, ensure_loaded, get_taxonomy_context
from app.services.tagging.chunk_tagging_service import tag_and_embed_document

__all__ = [
    "tag_chunk", "tag_chunks_batch", "tag_newspaper_article",
    "load_taxonomy", "ensure_loaded", "get_taxonomy_context",
    "tag_and_embed_document",
]
