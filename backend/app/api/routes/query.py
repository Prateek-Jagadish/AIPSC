"""
api/routes/query.py
────────────────────
The main question-answering endpoint.

This is what you call when you ask anything to the UPSC assistant.

Endpoints:
    POST /query                     — ask any question
    POST /query/answer              — specifically request a mains answer
    POST /query/probable-questions  — generate probable exam questions
    GET  /query/current-affairs     — fetch today's / recent CA digest
    POST /query/conversation/start  — start a new conversation session
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional
from loguru import logger

from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.current_affair import CurrentAffair
from app.services.retrieval.rag_pipeline import run_rag_pipeline
from app.services.retrieval.intent_detector import extract_word_limit
from app.core.rate_limiter import limiter, RATE_LLM_HEAVY, RATE_READ

router = APIRouter()


# ── Request / Response Schemas ────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000,
                       description="Your question or study request")
    conversation_id: Optional[int] = Field(
        default=None,
        description="Pass a conversation_id to maintain session memory"
    )
    word_limit: Optional[int] = Field(
        default=None,
        description="Word limit for answer-writing requests (default: 250)"
    )
    include_visuals: Optional[bool] = Field(
        default=True,
        description="Include maps/diagrams in retrieval"
    )


class QueryResponse(BaseModel):
    query:           str
    intent:          str
    conversation_id: Optional[int]
    answer:          dict
    sources:         dict


class StartConversationResponse(BaseModel):
    conversation_id: int
    message: str


# ── POST /query ───────────────────────────────────────────────────────────────

@router.post("/", response_model=QueryResponse)
@limiter.limit(RATE_LLM_HEAVY)
async def ask_query(
    request: Request,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    The main query endpoint — handles all question types:

    - Concept queries:        "Explain federalism"
    - PYQ analysis:           "Show PYQs on demand and supply"
    - Trend analysis:         "What are recurring themes in GS2 Polity?"
    - Mains answer writing:   "Write a 250-word answer on inflation"
    - Probable questions:     "Give me 5 probable questions on IVC"
    - Map queries:            "Which maps should I revise for Environment?"
    - Weakness check:         "Which topics am I lagging in?"
    - Revision:               "Give me my weekly cheat sheet"
    - Current affairs link:   "What current affairs relate to Federalism?"

    Optionally pass conversation_id to maintain session context.
    """
    if not body.query.strip():
        raise HTTPException(400, "Query cannot be empty.")

    word_limit = body.word_limit or extract_word_limit(body.query)

    logger.info(f"📨 Query: '{body.query[:80]}' | conv_id={body.conversation_id}")

    result = await run_rag_pipeline(
        db=db,
        query=body.query,
        conversation_id=body.conversation_id,
        word_limit=word_limit,
    )

    return QueryResponse(
        query=result["query"],
        intent=result["intent"],
        conversation_id=body.conversation_id,
        answer=result["answer"],
        sources=result["sources"],
    )


# ── POST /query/answer ────────────────────────────────────────────────────────

@router.post("/answer")
@limiter.limit(RATE_LLM_HEAVY)
async def write_mains_answer(
    request: Request,
    body: QueryRequest,
    answer_type: str = "full",   # "full" | "approach"
    db: AsyncSession = Depends(get_db),
):
    """
    Specifically request a mains answer or approach guide.

    answer_type=full     → complete structured answer
    answer_type=approach → study guide only (good for practice)
    """
    from app.services.retrieval.hybrid_search import hybrid_search
    from app.services.retrieval.rag_pipeline import handle_answer_writing

    word_limit = body.word_limit or extract_word_limit(body.query) or 250

    search_result = await hybrid_search(db=db, query=body.query)

    answer = await handle_answer_writing(
        query=body.query,
        search_result=search_result,
        word_limit=word_limit,
        answer_type=answer_type,
    )

    return {
        "query":       body.query,
        "answer_type": answer_type,
        "word_limit":  word_limit,
        "answer":      answer,
        "sources": {
            "chunks": len(search_result.chunks),
            "pyqs":   len(search_result.pyqs),
            "ca":     len(search_result.current_affairs),
        },
    }


# ── POST /query/probable-questions ───────────────────────────────────────────

@router.post("/probable-questions")
@limiter.limit(RATE_LLM_HEAVY)
async def get_probable_questions(
    request: Request,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate 5 probable exam questions for a topic.
    Mix of Mains + Prelims with probability ratings.
    """
    from app.services.retrieval.hybrid_search import hybrid_search
    from app.services.retrieval.rag_pipeline import handle_probable_questions

    search_result = await hybrid_search(db=db, query=body.query, include_visuals=False)
    questions = await handle_probable_questions(body.query, search_result)

    return {
        "query":     body.query,
        "questions": questions.get("questions", []),
    }


# ── GET /query/current-affairs ────────────────────────────────────────────────

@router.get("/current-affairs")
@limiter.limit(RATE_READ)
async def get_current_affairs_digest(
    request: Request,
    days: int = 7,
    topic_id: Optional[int] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch recent current affairs from the last N days.
    Optionally filter by topic_id.

    Returns a digest of UPSC-relevant articles with question angles.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import desc

    cutoff = datetime.utcnow() - timedelta(days=days)

    query = (
        select(CurrentAffair)
        .where(CurrentAffair.created_at >= cutoff)
        .order_by(desc(CurrentAffair.relevance_score))
        .limit(limit)
    )

    if topic_id:
        query = query.where(CurrentAffair.topic_id == topic_id)

    result = await db.execute(query)
    items  = result.scalars().all()

    return {
        "period_days": days,
        "total":       len(items),
        "items": [
            {
                "id":                ca.id,
                "date":              str(ca.newspaper_date),
                "headline":          ca.headline,
                "summary":           ca.summary,
                "upsc_angle":        ca.upsc_angle,
                "probable_question": ca.probable_question,
                "mains_dimensions":  ca.mains_dimensions,
                "prelims_facts":     ca.prelims_facts,
                "static_linkage":    ca.static_linkage,
                "relevance_score":   ca.relevance_score,
                "exam_relevance":    ca.exam_relevance.value if ca.exam_relevance else None,
            }
            for ca in items
        ],
    }


# ── POST /query/conversation/start ───────────────────────────────────────────

@router.post("/conversation/start", response_model=StartConversationResponse)
@limiter.limit(RATE_READ)
async def start_conversation(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new conversation session.
    Returns a conversation_id to pass in subsequent queries.

    Usage:
        1. Call POST /query/conversation/start → get conversation_id
        2. Pass conversation_id in every POST /query request
        3. The system tracks topics discussed for weakness detection
    """
    conv = Conversation()
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return StartConversationResponse(
        conversation_id=conv.id,
        message=(
            f"Session started (id={conv.id}). "
            "Pass this conversation_id in your queries to enable memory tracking."
        ),
    )


# ── GET /query/conversation/{id} ─────────────────────────────────────────────

@router.get("/conversation/{conversation_id}")
@limiter.limit(RATE_READ)
async def get_conversation_history(
    request: Request,
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the full history of a conversation session."""
    from app.models.conversation import ConversationTurn

    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, f"Conversation {conversation_id} not found.")

    turns_result = await db.execute(
        select(ConversationTurn)
        .where(ConversationTurn.conversation_id == conversation_id)
        .order_by(ConversationTurn.turn_number)
    )
    turns = turns_result.scalars().all()

    return {
        "conversation_id": conv.id,
        "started_at":      conv.created_at.isoformat() if conv.created_at else None,
        "turn_count":      conv.turn_count or 0,
        "turns": [
            {
                "turn":   t.turn_number,
                "query":  t.user_query,
                "intent": t.intent,
                "time":   t.created_at.isoformat() if t.created_at else None,
            }
            for t in turns
        ],
    }
