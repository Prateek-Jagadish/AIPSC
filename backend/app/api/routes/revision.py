"""
api/routes/revision.py
───────────────────────
Endpoints for generating revision plans and cheat sheets.

Endpoints:
    GET  /revision/weekly    — this week's personalised cheat sheet
    GET  /revision/monthly   — this month's revision plan
    POST /revision/topic     — quick revision notes for a specific topic
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from datetime import datetime, timedelta, date
from typing import Optional
from loguru import logger

from app.core.database import get_db
from app.models.topic import Topic
from app.models.current_affair import CurrentAffair
from app.models.pyq import PYQ
from app.models.user_stats import UserTopicStat, RevisionLog, RevisionType
from app.services.llm.llm_client import call_llm_json
from app.services.llm.prompts import revision_cheatsheet_prompt
from app.core.rate_limiter import limiter, RATE_LLM_HEAVY, RATE_READ
from pydantic import BaseModel

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _build_cheatsheet(
    db: AsyncSession,
    period_label: str,
    days_back: int,
    revision_type: RevisionType,
) -> dict:
    """
    Core cheat sheet builder used by both weekly and monthly endpoints.

    1. Fetches user stats for topics studied in this period
    2. Fetches current affairs from this period
    3. Fetches high-weight PYQ topics
    4. Calls GPT-4o to generate the cheat sheet
    5. Saves a RevisionLog record
    """
    cutoff = datetime.utcnow() - timedelta(days=days_back)

    # Topics studied (by last_revised date)
    stats_result = await db.execute(
        select(UserTopicStat, Topic)
        .join(Topic, Topic.id == UserTopicStat.topic_id)
        .where(UserTopicStat.last_revised >= cutoff)
        .order_by(desc(UserTopicStat.revision_count))
        .limit(20)
    )
    studied = stats_result.all()

    topics_studied_str = ", ".join(
        f"{t.name} (coverage: {round(s.coverage_score, 1)})"
        for s, t in studied
    ) or "No topics recorded yet"

    # Weak areas
    weak_result = await db.execute(
        select(UserTopicStat, Topic)
        .join(Topic, Topic.id == UserTopicStat.topic_id)
        .where(UserTopicStat.weakness_score >= 6.0)
        .order_by(desc(UserTopicStat.weakness_score))
        .limit(10)
    )
    weak_areas_str = ", ".join(
        t.name for _, t in weak_result.all()
    ) or "None detected yet"

    # Current affairs this period
    ca_result = await db.execute(
        select(CurrentAffair)
        .where(CurrentAffair.created_at >= cutoff)
        .order_by(desc(CurrentAffair.relevance_score))
        .limit(15)
    )
    cas = ca_result.scalars().all()
    ca_summary = "\n".join(
        f"- {ca.headline} [{str(ca.newspaper_date)}]"
        for ca in cas
    ) or "No current affairs uploaded this period"

    # High-frequency PYQ topics
    pyq_result = await db.execute(
        select(Topic.name, func.count(PYQ.id).label("cnt"))
        .join(PYQ, PYQ.topic_id == Topic.id, isouter=True)
        .group_by(Topic.name)
        .order_by(desc("cnt"))
        .limit(10)
    )
    pyq_trends = ", ".join(
        f"{row.name} ({row.cnt} PYQs)"
        for row in pyq_result.fetchall()
        if row.cnt and row.cnt > 0
    ) or "No PYQ data yet"

    # Generate cheat sheet with GPT-4o
    prompt = revision_cheatsheet_prompt(
        period_label=period_label,
        topics_studied=topics_studied_str,
        weak_areas=weak_areas_str,
        current_affairs_summary=ca_summary,
        pyq_trends=pyq_trends,
    )

    cheatsheet = await call_llm_json(prompt)

    # Save revision log
    log = RevisionLog(
        revision_type=revision_type,
        period_label=period_label,
        weak_areas=weak_areas_str,
        ca_highlights=ca_summary,
        cheat_sheet=str(cheatsheet),
    )
    db.add(log)
    await db.commit()

    return {
        "period":         period_label,
        "cheatsheet":     cheatsheet,
        "raw_data": {
            "topics_studied":  topics_studied_str,
            "weak_areas":      weak_areas_str,
            "ca_this_period":  len(cas),
        },
    }


# ── GET /revision/weekly ──────────────────────────────────────────────────────

@router.get("/weekly")
@limiter.limit(RATE_LLM_HEAVY)
async def get_weekly_revision(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate this week's personalised revision cheat sheet.

    Combines:
        - Topics you studied this week
        - Weak areas detected
        - Current affairs from this week
        - High-frequency PYQ topics
        - Probable questions to practice
    """
    today = datetime.utcnow()
    week_label = f"Week of {today.strftime('%d %b %Y')}"

    return await _build_cheatsheet(
        db=db,
        period_label=week_label,
        days_back=7,
        revision_type=RevisionType.WEEKLY,
    )


# ── GET /revision/monthly ─────────────────────────────────────────────────────

@router.get("/monthly")
@limiter.limit(RATE_LLM_HEAVY)
async def get_monthly_revision(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate this month's comprehensive revision plan.

    More detailed than weekly — includes:
        - Full topic movement over the month
        - Repeated weak spots
        - Most and least covered areas
        - Recommended next-month priority order
    """
    today = datetime.utcnow()
    month_label = today.strftime("%B %Y")

    return await _build_cheatsheet(
        db=db,
        period_label=month_label,
        days_back=30,
        revision_type=RevisionType.MONTHLY,
    )


# ── POST /revision/topic ──────────────────────────────────────────────────────

class TopicRevisionRequest(BaseModel):
    topic: str
    depth: str = "quick"   # "quick" | "deep"


@router.post("/topic")
@limiter.limit(RATE_LLM_HEAVY)
async def get_topic_revision(
    request: Request,
    body: TopicRevisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate quick revision notes for a specific topic on demand.
    Pulls from your stored notes, PYQs, and current affairs.
    """
    from app.services.retrieval.hybrid_search import hybrid_search

    search = await hybrid_search(
        db=db,
        query=f"revision notes on {body.topic}",
        include_pyqs=True,
        include_ca=True,
        include_visuals=True,
    )

    from app.services.retrieval.rag_pipeline import build_context_string, build_ca_string
    context = build_context_string(search)
    ca_str  = build_ca_string(search.current_affairs)
    pyq_str = "\n".join(f"- ({p.year} {p.paper}) {p.text[:100]}" for p in search.pyqs)

    depth_note = (
        "Give a compact 2-3 line summary per subtopic."
        if body.depth == "quick"
        else "Give detailed notes with examples, data, and case studies."
    )

    prompt = f"""You are a UPSC expert creating revision notes for: {body.topic}

DEPTH: {body.depth} ({depth_note})

STUDY MATERIAL CONTEXT:
{context}

PREVIOUS YEAR QUESTIONS:
{pyq_str or 'None found'}

CURRENT AFFAIRS:
{ca_str}

Create structured revision notes.
Return ONLY valid JSON:
{{
  "topic": "{body.topic}",
  "key_concepts": ["concept1", "concept2"],
  "important_facts": ["fact1", "fact2"],
  "pyq_angles": ["angle1", "angle2"],
  "current_affairs_connection": "how CA connects",
  "mains_dimensions": ["dim1", "dim2"],
  "prelims_facts": ["fact1", "fact2"],
  "diagram_reminder": "any diagram to draw? or null",
  "revision_summary": "2-3 line quick summary to read before exam"
}}"""

    notes = await call_llm_json(prompt)

    return {
        "topic":   body.topic,
        "depth":   body.depth,
        "notes":   notes,
        "sources": {
            "chunks": len(search.chunks),
            "pyqs":   len(search.pyqs),
            "ca":     len(search.current_affairs),
            "visuals": len(search.visuals),
        },
    }


# ── GET /revision/history ─────────────────────────────────────────────────────

@router.get("/history")
@limiter.limit(RATE_READ)
async def get_revision_history(
    request: Request,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Returns past revision sessions."""
    result = await db.execute(
        select(RevisionLog)
        .order_by(desc(RevisionLog.generated_at))
        .limit(limit)
    )
    logs = result.scalars().all()

    return {
        "total": len(logs),
        "sessions": [
            {
                "id":           log.id,
                "type":         log.revision_type.value,
                "period":       log.period_label,
                "generated_at": log.generated_at.isoformat() if log.generated_at else None,
                "user_rating":  log.user_rating,
            }
            for log in logs
        ],
    }
