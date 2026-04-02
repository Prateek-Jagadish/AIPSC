"""
api/routes/analytics.py
────────────────────────
Endpoints for preparation analytics, weakness detection,
and study pattern analysis.

Endpoints:
    GET /analytics/weakness         — top weak areas with reasons
    GET /analytics/coverage         — topic coverage overview
    GET /analytics/pyq-trends       — PYQ frequency analysis
    GET /analytics/ca-summary       — current affairs topic distribution
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional
from loguru import logger

from app.core.database import get_db
from app.models.topic import Topic, Subtopic, MicroTag
from app.models.pyq import PYQ
from app.models.current_affair import CurrentAffair
from app.models.user_stats import UserTopicStat, UserMicroTagStat
from app.services.intelligence.weakness_detection_service import compute_weakness_report
from app.services.llm.llm_client import call_llm_json
from app.services.llm.prompts import weakness_summary_prompt
from app.core.rate_limiter import limiter, RATE_LLM_MEDIUM, RATE_READ

router = APIRouter()


# ── GET /analytics/weakness ───────────────────────────────────────────────────

@router.get("/weakness")
@limiter.limit(RATE_LLM_MEDIUM)
async def get_weakness_analysis(
    request: Request,
    top_n: int = Query(default=10, description="Number of weak areas to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the top N areas where preparation is weakest.
    Uses the full weakness detection engine with anomaly detection.
    """
    report = await compute_weakness_report(db)

    return {
        "critical":       [vars(w) for w in report.critical],
        "high":           [vars(w) for w in report.high],
        "medium":         [vars(w) for w in report.medium],
        "anomalies":      [vars(w) for w in report.anomalies],
        "priority_order": report.priority_order,
        "message": (
            f"{len(report.critical)} critical gaps detected. "
            f"Focus on: {', '.join(report.priority_order[:3])}"
            if report.critical
            else "No critical gaps found. Keep revising!"
        ),
    }


# ── GET /analytics/coverage ───────────────────────────────────────────────────

@router.get("/coverage")
@limiter.limit(RATE_READ)
async def get_coverage_overview(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a full topic-by-topic coverage overview.
    Shows which topics are strong, medium, or weak.
    """
    result = await db.execute(
        select(UserTopicStat, Topic)
        .join(Topic, Topic.id == UserTopicStat.topic_id)
        .order_by(Topic.paper, Topic.name)
    )
    rows = result.all()

    by_paper: dict = {}
    for stat, topic in rows:
        paper = topic.paper.value
        if paper not in by_paper:
            by_paper[paper] = []
        by_paper[paper].append({
            "topic":          topic.name,
            "coverage":       round(stat.coverage_score, 1),
            "weakness":       round(stat.weakness_score, 1),
            "revisions":      stat.revision_count,
            "questions_asked": stat.question_count,
            "last_revised":   stat.last_revised.isoformat() if stat.last_revised else "Never",
            "is_anomaly":     stat.is_anomaly,
        })

    return {"coverage_by_paper": by_paper}


# ── GET /analytics/pyq-trends ─────────────────────────────────────────────────

@router.get("/pyq-trends")
@limiter.limit(RATE_READ)
async def get_pyq_trends(
    request: Request,
    paper: Optional[str] = Query(default=None, description="Filter by paper: GS1/GS2/GS3/GS4/Essay"),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyzes PYQ frequency and patterns:
    - Which topics appear most often
    - Year-wise distribution
    - Command word frequency
    """
    query = select(
        PYQ.topic_id,
        PYQ.paper,
        PYQ.year,
        PYQ.command_word,
        func.count(PYQ.id).label("count"),
        Topic.name.label("topic_name"),
    ).join(Topic, Topic.id == PYQ.topic_id, isouter=True)

    if paper:
        from app.models.pyq import GSSPaper
        try:
            query = query.where(PYQ.paper == GSSPaper(paper))
        except ValueError:
            pass

    query = query.group_by(
        PYQ.topic_id, PYQ.paper, PYQ.year, PYQ.command_word, Topic.name
    ).order_by(desc("count"))

    result = await db.execute(query)
    rows   = result.fetchall()

    # Aggregate by topic
    topic_freq: dict = {}
    year_dist:  dict = {}
    cmd_freq:   dict = {}

    for row in rows:
        tname = row.topic_name or f"Topic {row.topic_id}"
        topic_freq[tname] = topic_freq.get(tname, 0) + row.count

        if row.year:
            year_dist[str(row.year)] = year_dist.get(str(row.year), 0) + row.count

        if row.command_word:
            cw = str(row.command_word)
            cmd_freq[cw] = cmd_freq.get(cw, 0) + row.count

    return {
        "topic_frequency": dict(sorted(topic_freq.items(), key=lambda x: x[1], reverse=True)),
        "year_distribution": dict(sorted(year_dist.items())),
        "command_word_frequency": dict(sorted(cmd_freq.items(), key=lambda x: x[1], reverse=True)),
    }


# ── GET /analytics/ca-summary ─────────────────────────────────────────────────

@router.get("/ca-summary")
@limiter.limit(RATE_READ)
async def get_ca_topic_summary(
    request: Request,
    days: int = Query(default=30, description="Look back N days"),
    db: AsyncSession = Depends(get_db),
):
    """
    Shows which UPSC topics are most active in recent current affairs.
    Helps you know where to focus for a current affairs-heavy exam.
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            CurrentAffair.topic_id,
            Topic.name.label("topic_name"),
            func.count(CurrentAffair.id).label("article_count"),
            func.avg(CurrentAffair.relevance_score).label("avg_relevance"),
        )
        .join(Topic, Topic.id == CurrentAffair.topic_id, isouter=True)
        .where(CurrentAffair.created_at >= cutoff)
        .group_by(CurrentAffair.topic_id, Topic.name)
        .order_by(desc("article_count"))
    )
    rows = result.fetchall()

    return {
        "period_days": days,
        "topics": [
            {
                "topic":          r.topic_name or "Untagged",
                "article_count":  r.article_count,
                "avg_relevance":  round(float(r.avg_relevance or 0), 1),
            }
            for r in rows
        ],
    }
