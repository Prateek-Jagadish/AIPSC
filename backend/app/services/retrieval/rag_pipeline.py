"""
services/retrieval/rag_pipeline.py
────────────────────────────────────
The RAG (Retrieval-Augmented Generation) pipeline.

Takes a user query → retrieves relevant context → generates a
structured UPSC-tutor response.

Query types handled:
    1. CONCEPT_QUERY      → explain topic + link CAs + show PYQs
    2. PYQ_SEARCH         → find and analyze past questions
    3. TREND_ANALYSIS     → analyze PYQ patterns over years
    4. ANSWER_WRITING     → generate full mains answer
    5. PROBABLE_QUESTIONS → generate 5 probable questions
    6. MAP_QUERY          → retrieve maps/visuals + describe them
    7. WEAKNESS_CHECK     → analyze preparation gaps
    8. REVISION           → generate cheat sheet
    9. GENERAL            → fallback — best effort answer

Output structure (always returned as structured dict):
    {
        "intent":          str,
        "answer":          str,
        "pyqs":            [...],
        "current_affairs": [...],
        "visuals":         [...],
        "probable_questions": [...],
        "follow_up_suggestions": [...],
    }
"""

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import json

from app.services.retrieval.hybrid_search import hybrid_search, HybridSearchResult
from app.services.retrieval.intent_detector import detect_intent, QueryIntent
from app.services.llm.llm_client import call_llm_json
from app.services.llm.prompts import (
    generate_answer_prompt,
    probable_questions_prompt,
)
from app.core.config import settings


# ── Context Builder ───────────────────────────────────────────────────────────

def build_context_string(search_result: HybridSearchResult) -> str:
    """
    Formats retrieved chunks into a clean context string for the LLM.
    Includes source labels so the LLM knows where each piece comes from.
    """
    parts = []

    if search_result.chunks:
        parts.append("=== STUDY MATERIAL / NOTES ===")
        for i, c in enumerate(search_result.chunks[:settings.FINAL_CONTEXT_LIMIT], 1):
            topic_label = f"[{c.topic_name} > {c.subtopic_name}]" if c.topic_name else ""
            parts.append(f"[{i}] {topic_label}\n{c.text}\n")

    if search_result.pyqs:
        parts.append("=== PREVIOUS YEAR QUESTIONS (PYQs) ===")
        for i, p in enumerate(search_result.pyqs, 1):
            year_paper = f"({p.year} | {p.paper})" if p.year else ""
            parts.append(f"[PYQ {i}] {year_paper}\nQ: {p.text}\n")

    if search_result.current_affairs:
        parts.append("=== CURRENT AFFAIRS ===")
        for i, ca in enumerate(search_result.current_affairs, 1):
            date_label = f"[{ca.date}]" if ca.date else ""
            headline   = f"**{ca.headline}**\n" if ca.headline else ""
            parts.append(f"[CA {i}] {date_label}\n{headline}{ca.text}\n")

    return "\n".join(parts)


def build_pyq_history_string(pyqs: list) -> str:
    """Formats PYQs as a compact history string for probable questions prompt."""
    if not pyqs:
        return "No PYQs found for this topic."
    lines = []
    for p in pyqs:
        year_paper = f"{p.year} {p.paper}" if p.year else ""
        lines.append(f"- [{year_paper}] {p.text[:150]}")
    return "\n".join(lines)


def build_ca_string(cas: list) -> str:
    """Formats current affairs as a compact string."""
    if not cas:
        return "No recent current affairs found."
    lines = []
    for ca in cas:
        date = f"[{ca.date}] " if ca.date else ""
        lines.append(f"- {date}{ca.headline or ca.text[:100]}")
    return "\n".join(lines)


# ── Intent-specific Handlers ──────────────────────────────────────────────────

async def handle_concept_query(
    query: str,
    search_result: HybridSearchResult,
) -> dict:
    """
    Handles: "Explain federalism" / "What is demand-supply?"

    Returns a comprehensive response:
        - concept explanation from notes
        - PYQs on this topic
        - current affairs linkage
        - probable question angles
    """
    context = build_context_string(search_result)

    prompt = f"""You are a UPSC expert tutor.

STUDENT QUERY: {query}

RETRIEVED CONTEXT:
{context}

Provide a comprehensive UPSC-focused response. Include:
1. Clear concept explanation (draw from the context)
2. UPSC relevance (which GS paper, mains vs prelims)
3. Current affairs linkage (if any from the context)
4. Key facts for Prelims
5. Answer-writing dimensions for Mains
6. 2-3 follow-up study suggestions

Return ONLY valid JSON:
{{
  "concept_explanation": "clear explanation",
  "gs_paper": "GS1/GS2/GS3/GS4",
  "exam_focus": "Mains / Prelims / Both",
  "current_affairs_linkage": "how this connects to recent news",
  "prelims_key_facts": ["fact1", "fact2", "fact3"],
  "mains_dimensions": ["dimension1", "dimension2", "dimension3"],
  "diagram_relevant": false,
  "diagram_suggestion": null,
  "follow_up_suggestions": ["suggestion1", "suggestion2"]
}}"""

    result = await call_llm_json(prompt)
    return result or {"concept_explanation": "Could not generate response.", "follow_up_suggestions": []}


async def handle_pyq_analysis(
    query: str,
    search_result: HybridSearchResult,
) -> dict:
    """
    Handles: "What are recurring PYQ themes in GS2 Polity?"
    Analyzes PYQ patterns, trends, command words, frequency.
    """
    pyq_history = build_pyq_history_string(search_result.pyqs)

    prompt = f"""You are a UPSC expert analyzing Previous Year Question patterns.

STUDENT QUERY: {query}

PYQ DATA RETRIEVED:
{pyq_history}

Analyze the PYQ patterns and provide:
1. Recurring themes
2. Year-wise trend
3. Common command words (discuss/analyze/examine/etc.)
4. Static vs current affairs balance
5. Topics that deserve highest revision priority

Return ONLY valid JSON:
{{
  "recurring_themes": ["theme1", "theme2"],
  "year_wise_trend": "description of trend",
  "common_command_words": ["discuss", "analyze"],
  "static_vs_ca_balance": "description",
  "high_priority_topics": ["topic1", "topic2"],
  "pattern_insight": "2-3 line key insight for the student",
  "revision_priority": ["priority1", "priority2", "priority3"]
}}"""

    return await call_llm_json(prompt) or {}


async def handle_answer_writing(
    query: str,
    search_result: HybridSearchResult,
    word_limit: int = 250,
    answer_type: str = "full",
) -> dict:
    """
    Handles: "Write a 250-word GS3 answer on inflation"
    Generates a full structured mains answer or approach guide.
    """
    context = build_context_string(search_result)
    ca_str  = build_ca_string(search_result.current_affairs)

    prompt = generate_answer_prompt(
        question=query,
        word_limit=word_limit,
        context_chunks=context,
        current_affairs=ca_str,
        answer_type=answer_type,
    )

    return await call_llm_json(prompt) or {}


async def handle_probable_questions(
    query: str,
    search_result: HybridSearchResult,
) -> dict:
    """
    Handles: "Give me 5 probable questions on Federalism"
    Generates prediction-based questions from PYQ trends + current affairs.
    """
    topic_name    = search_result.chunks[0].topic_name    if search_result.chunks else query
    subtopic_name = search_result.chunks[0].subtopic_name if search_result.chunks else ""
    pyq_history   = build_pyq_history_string(search_result.pyqs)
    ca_str        = build_ca_string(search_result.current_affairs)

    prompt = probable_questions_prompt(
        topic=topic_name,
        subtopic=subtopic_name,
        pyq_history=pyq_history,
        current_affairs=ca_str,
    )

    return await call_llm_json(prompt) or {}


async def handle_map_query(
    query: str,
    search_result: HybridSearchResult,
) -> dict:
    """
    Handles: "Which maps should I refer for Western Ghats?"
    Returns visual assets with descriptions and exam use cases.
    """
    visuals_info = []
    for v in search_result.visuals:
        visuals_info.append({
            "type":       v.image_type,
            "topic":      v.topic_name,
            "description": v.text,
            "image_path": v.image_path,
        })

    prompt = f"""You are a UPSC expert advising on map/diagram study.

STUDENT QUERY: {query}

VISUAL ASSETS FOUND:
{json.dumps(visuals_info, indent=2)}

CONTEXT FROM NOTES:
{build_context_string(search_result)}

Provide:
1. Which visuals are most important and why
2. What to memorize from each
3. How each could appear in exam
4. Exam strategy for map-based questions

Return ONLY valid JSON:
{{
  "important_visuals": [
    {{
      "image_path": "path",
      "type": "Map/Table/Graph",
      "what_to_memorize": "specific items",
      "exam_angle": "how it could appear",
      "mains_use": "use in answer writing"
    }}
  ],
  "map_study_strategy": "2-3 line strategy",
  "geo_entities_to_revise": ["entity1", "entity2"]
}}"""

    result = await call_llm_json(prompt) or {}
    result["raw_visuals"] = visuals_info   # always include raw image paths
    return result


# ── Main RAG Pipeline ─────────────────────────────────────────────────────────

async def run_rag_pipeline(
    db: AsyncSession,
    query: str,
    conversation_id: int = None,
    word_limit: int = 250,
) -> dict:
    """
    The main entry point for all user queries.

    Steps:
        1. Detect query intent
        2. Run hybrid search (vector + keyword)
        3. Route to the correct handler based on intent
        4. Build the final structured response
        5. Store conversation turn (if conversation_id provided)

    Returns a structured dict ready for the API response.
    """
    logger.info(f"🧠 RAG pipeline: '{query[:80]}'")

    # Step 1: Detect intent
    intent = await detect_intent(query)
    logger.info(f"  Intent: {intent}")

    # Step 2: Hybrid search
    search_result = await hybrid_search(
        db=db,
        query=query,
        include_pyqs=True,
        include_ca=True,
        include_visuals=(intent == QueryIntent.MAP_QUERY),
    )

    # Step 3: Route to handler
    handler_result = {}

    if intent == QueryIntent.CONCEPT_QUERY:
        handler_result = await handle_concept_query(query, search_result)

    elif intent == QueryIntent.PYQ_SEARCH:
        handler_result = await handle_pyq_analysis(query, search_result)

    elif intent == QueryIntent.TREND_ANALYSIS:
        handler_result = await handle_pyq_analysis(query, search_result)

    elif intent == QueryIntent.ANSWER_WRITING:
        handler_result = await handle_answer_writing(query, search_result, word_limit)

    elif intent == QueryIntent.PROBABLE_QUESTIONS:
        handler_result = await handle_probable_questions(query, search_result)

    elif intent == QueryIntent.MAP_QUERY:
        handler_result = await handle_map_query(query, search_result)

    else:
        # GENERAL fallback — concept query handler works well
        handler_result = await handle_concept_query(query, search_result)

    # Step 4: Build final response
    response = {
        "query":   query,
        "intent":  intent.value,
        "answer":  handler_result,
        "sources": {
            "chunks": [
                {"id": c.source_id, "topic": c.topic_name, "score": round(c.score, 3)}
                for c in search_result.chunks
            ],
            "pyqs": [
                {"id": p.source_id, "year": p.year, "paper": p.paper, "score": round(p.score, 3)}
                for p in search_result.pyqs
            ],
            "current_affairs": [
                {"id": ca.source_id, "headline": ca.headline, "date": ca.date}
                for ca in search_result.current_affairs
            ],
            "visuals": [
                {"id": v.source_id, "type": v.image_type, "image_path": v.image_path}
                for v in search_result.visuals
            ],
        },
    }

    # Step 5: Store conversation turn
    if conversation_id:
        await _store_conversation_turn(
            db=db,
            conversation_id=conversation_id,
            query=query,
            response=response,
            intent=intent,
            search_result=search_result,
        )

    logger.info(f"✅ RAG pipeline complete for intent={intent}")
    return response


# ── Conversation Storage ──────────────────────────────────────────────────────

async def _store_conversation_turn(
    db: AsyncSession,
    conversation_id: int,
    query: str,
    response: dict,
    intent,
    search_result: HybridSearchResult,
) -> None:
    """
    Persists the conversation turn and its topic coverage to the DB.
    Powers the weakness detection and revision system.
    """
    from app.models.conversation import ConversationTurn, ConversationTopic, Conversation
    from sqlalchemy import select, update

    try:
        # Get current turn count
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = conv_result.scalar_one_or_none()
        if not conv:
            return

        turn_number = (conv.turn_count or 0) + 1

        # Create turn
        turn = ConversationTurn(
            conversation_id=conversation_id,
            turn_number=turn_number,
            user_query=query,
            assistant_reply=json.dumps(response.get("answer", {})),
            intent=intent.value,
        )
        db.add(turn)
        await db.flush()

        # Store topic coverage from search results
        # Build ConversationTopic records linking this turn to the
        # topics/subtopics/micro_tags that were retrieved and discussed.
        # This is the critical bridge that powers weakness detection.
        seen_topics = set()
        for item in search_result.chunks + search_result.pyqs + search_result.current_affairs:
            # Each RetrievedChunk carries topic_name/subtopic_name but we need IDs.
            # The hybrid search stored topic_ids on the result; retrieve per-item
            # IDs from the taxonomy cache by name matching.
            from app.services.tagging.taxonomy_cache import _cache, ensure_loaded
            await ensure_loaded(db)

            topic_id = _cache.get("topic_name_to_id", {}).get(item.topic_name)
            subtopic_id = _cache.get("subtopic_name_to_id", {}).get(item.subtopic_name)
            micro_tag_id = _cache.get("microtag_name_to_id", {}).get(item.micro_tag_name) if hasattr(item, "micro_tag_name") else None

            # Deduplicate by (topic_id, subtopic_id, micro_tag_id)
            key = (topic_id, subtopic_id, micro_tag_id)
            if key in seen_topics or not topic_id:
                continue
            seen_topics.add(key)

            ct = ConversationTopic(
                turn_id=turn.id,
                topic_id=topic_id,
                subtopic_id=subtopic_id,
                micro_tag_id=micro_tag_id,
                confidence=0.5,
            )
            db.add(ct)

        # Update conversation turn count
        conv.turn_count = turn_number

        # Update coverage scores from detected topics
        if search_result.topic_ids:
            from app.services.intelligence.weakness_detection_service import (
                update_coverage_from_conversation,
            )
            await update_coverage_from_conversation(
                db=db,
                topic_ids=search_result.topic_ids,
                quality_score=0.5,
            )

        await db.commit()

    except Exception as e:
        logger.warning(f"Could not store conversation turn: {e}")
