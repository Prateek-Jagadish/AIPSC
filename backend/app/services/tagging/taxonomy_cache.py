"""
services/tagging/taxonomy_cache.py
────────────────────────────────────
In-memory cache of the UPSC topic taxonomy.

Why this exists:
    Every chunk that gets tagged needs to know the full list of
    topics / subtopics / micro_tags so the LLM can pick from them.
    Hitting the DB for every chunk would be very slow.

    This module loads the taxonomy ONCE at startup (or on first use)
    and keeps it in memory for the lifetime of the process.
    It also builds a fast lookup dict: name → id.

Usage:
    from app.services.tagging.taxonomy_cache import get_taxonomy_context, resolve_tag_ids
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
import json
from typing import Optional

from app.models.topic import Topic, Subtopic, MicroTag


# ── In-memory Cache ───────────────────────────────────────────────────────────

_cache: dict = {
    "loaded": False,
    "taxonomy_json": "",          # JSON string passed to LLM prompts
    "topic_name_to_id": {},       # "Polity" → 1
    "subtopic_name_to_id": {},    # "Federalism" → 5
    "microtag_name_to_id": {},    # "GST Council" → 42
}


# ── Loader ────────────────────────────────────────────────────────────────────

async def load_taxonomy(db: AsyncSession) -> None:
    """
    Loads the full topic taxonomy from DB into the in-memory cache.
    Call once at app startup (or lazily on first tagging request).
    """
    logger.info("🧠 Loading UPSC taxonomy into memory...")

    # Load all topics
    topics_result = await db.execute(select(Topic).order_by(Topic.id))
    topics = topics_result.scalars().all()

    # Load all subtopics
    subtopics_result = await db.execute(select(Subtopic).order_by(Subtopic.id))
    subtopics = subtopics_result.scalars().all()

    # Load all micro_tags
    microtags_result = await db.execute(select(MicroTag).order_by(MicroTag.id))
    microtags = microtags_result.scalars().all()

    # Build lookup dicts
    topic_map    = {t.id: t for t in topics}
    subtopic_map = {s.id: s for s in subtopics}

    # Build taxonomy tree for the LLM prompt
    tree = []
    for topic in topics:
        topic_subtopics = [s for s in subtopics if s.topic_id == topic.id]
        topic_entry = {
            "topic": topic.name,
            "paper": topic.paper.value,
            "subtopics": []
        }
        for sub in topic_subtopics:
            sub_microtags = [m.name for m in microtags if m.subtopic_id == sub.id]
            topic_entry["subtopics"].append({
                "subtopic": sub.name,
                "micro_tags": sub_microtags
            })
        tree.append(topic_entry)

    # Build name → id lookup dicts
    topic_name_to_id    = {t.name: t.id for t in topics}
    subtopic_name_to_id = {s.name: s.id for s in subtopics}
    microtag_name_to_id = {m.name: m.id for m in microtags}

    # Update cache
    _cache["loaded"]              = True
    _cache["taxonomy_json"]       = json.dumps(tree, indent=2)
    _cache["topic_name_to_id"]    = topic_name_to_id
    _cache["subtopic_name_to_id"] = subtopic_name_to_id
    _cache["microtag_name_to_id"] = microtag_name_to_id

    logger.info(
        f"✅ Taxonomy loaded: {len(topics)} topics | "
        f"{len(subtopics)} subtopics | {len(microtags)} micro_tags"
    )


async def ensure_loaded(db: AsyncSession) -> None:
    """Loads the taxonomy if not already cached."""
    if not _cache["loaded"]:
        await load_taxonomy(db)


def invalidate_cache() -> None:
    """Call this if the taxonomy is updated at runtime."""
    _cache["loaded"] = False
    logger.info("🔄 Taxonomy cache invalidated")


# ── Public API ────────────────────────────────────────────────────────────────

def get_taxonomy_context() -> str:
    """
    Returns the taxonomy as a JSON string suitable for LLM prompts.
    Must call ensure_loaded() before this.
    """
    return _cache["taxonomy_json"]


def resolve_tag_ids(
    topic_name: Optional[str],
    subtopic_name: Optional[str],
    microtag_name: Optional[str],
) -> dict:
    """
    Converts LLM-returned name strings into database IDs.

    Returns:
        {
            "topic_id": int | None,
            "subtopic_id": int | None,
            "micro_tag_id": int | None,
        }

    Uses fuzzy fallback: if exact match fails, tries case-insensitive match.
    """
    def lookup(name_map: dict, name: Optional[str]) -> Optional[int]:
        if not name:
            return None
        # Exact match
        if name in name_map:
            return name_map[name]
        # Case-insensitive fallback
        name_lower = name.lower()
        for key, val in name_map.items():
            if key.lower() == name_lower:
                return val
        # Partial match fallback (last resort)
        for key, val in name_map.items():
            if name_lower in key.lower() or key.lower() in name_lower:
                return val
        return None

    return {
        "topic_id":    lookup(_cache["topic_name_to_id"],    topic_name),
        "subtopic_id": lookup(_cache["subtopic_name_to_id"], subtopic_name),
        "micro_tag_id": lookup(_cache["microtag_name_to_id"], microtag_name),
    }
