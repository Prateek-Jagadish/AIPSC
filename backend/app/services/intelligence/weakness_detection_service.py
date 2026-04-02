"""
services/intelligence/weakness_detection_service.py
─────────────────────────────────────────────────────
The study intelligence layer — detects preparation gaps
and anomalies by cross-referencing:

    - Topics you've discussed (from ConversationTopic)
    - PYQ importance weights (from MicroTag.pyq_weight)
    - Current affairs pressure (from CurrentAffair count by topic)
    - Time since last revision (from UserTopicStat.last_revised)

Anomaly = topic with HIGH PYQ weight but ZERO or LOW coverage
         AND appearing in recent current affairs

This powers:
    GET /analytics/weakness
    GET /revision/weekly
    GET /revision/monthly
    "Which topics am I lagging in?"
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from app.models.topic import Topic, Subtopic, MicroTag
from app.models.pyq import PYQ
from app.models.current_affair import CurrentAffair
from app.models.conversation import ConversationTopic
from app.models.user_stats import UserTopicStat, UserMicroTagStat, WeaknessLevel


# ── Data Types ────────────────────────────────────────────────────────────────

@dataclass
class WeakArea:
    topic_id:         int
    topic_name:       str
    paper:            str
    pyq_weight:       float       # how important in exam (1–10)
    coverage_score:   float       # how much student has studied (0–10)
    gap_score:        float       # pyq_weight - coverage_score
    ca_pressure:      int         # recent current affairs count
    days_since_revision: int
    is_anomaly:       bool        # critical: high weight, zero coverage
    reason:           str         # plain-language explanation


@dataclass
class WeaknessReport:
    critical:   list[WeakArea]   # gap_score >= 7
    high:       list[WeakArea]   # gap_score 5–7
    medium:     list[WeakArea]   # gap_score 3–5
    anomalies:  list[WeakArea]   # never touched, high PYQ weight
    priority_order: list[str]    # ordered topic names to study next


# ── Core Engine ───────────────────────────────────────────────────────────────

async def compute_weakness_report(
    db: AsyncSession,
    ca_lookback_days: int = 30,
) -> WeaknessReport:
    """
    Computes the full weakness report.

    Steps:
        1. Load all topics with their PYQ weight (priority_score)
        2. Load user coverage stats
        3. Count recent CA articles per topic
        4. Compute gap_score and anomaly flags
        5. Sort and categorize

    Returns WeaknessReport with critical / high / medium / anomaly buckets.
    """
    logger.info("📊 Computing weakness report...")

    # Load all topics
    topics_result = await db.execute(
        select(Topic).order_by(Topic.priority_score.desc())
    )
    topics = topics_result.scalars().all()

    # Load user stats (keyed by topic_id)
    stats_result = await db.execute(select(UserTopicStat))
    stats_map = {s.topic_id: s for s in stats_result.scalars().all()}

    # Count recent CA articles per topic
    ca_cutoff = datetime.utcnow() - timedelta(days=ca_lookback_days)
    ca_result = await db.execute(
        select(CurrentAffair.topic_id, func.count(CurrentAffair.id).label("cnt"))
        .where(CurrentAffair.created_at >= ca_cutoff)
        .group_by(CurrentAffair.topic_id)
    )
    ca_count_map = {row.topic_id: row.cnt for row in ca_result.fetchall()}

    # Build weak areas
    weak_areas: list[WeakArea] = []

    for topic in topics:
        stat = stats_map.get(topic.id)

        coverage  = stat.coverage_score if stat else 0.0
        pyq_wt    = topic.priority_score
        gap       = max(0.0, pyq_wt - coverage)
        ca_press  = ca_count_map.get(topic.id, 0)
        is_anomaly = (coverage < 1.0 and pyq_wt >= 7.0)

        last_rev  = stat.last_revised if stat else None
        days_ago  = (
            (datetime.utcnow() - last_rev).days
            if last_rev else 9999
        )

        # Build reason string
        reason_parts = []
        if is_anomaly:
            reason_parts.append("⚠️  Never studied — high exam weight")
        if ca_press >= 3:
            reason_parts.append(f"📰 {ca_press} recent CA articles")
        if days_ago > 14 and days_ago < 9999:
            reason_parts.append(f"🗓  Last revised {days_ago} days ago")
        if days_ago == 9999:
            reason_parts.append("🗓  Never revised")

        reason = " | ".join(reason_parts) if reason_parts else "Gap detected"

        weak_areas.append(WeakArea(
            topic_id=topic.id,
            topic_name=topic.name,
            paper=topic.paper.value,
            pyq_weight=round(pyq_wt, 1),
            coverage_score=round(coverage, 1),
            gap_score=round(gap, 1),
            ca_pressure=ca_press,
            days_since_revision=days_ago if days_ago < 9999 else -1,
            is_anomaly=is_anomaly,
            reason=reason,
        ))

    # Sort by gap_score descending
    weak_areas.sort(key=lambda x: (x.is_anomaly, x.gap_score), reverse=True)

    critical  = [w for w in weak_areas if w.gap_score >= 7.0]
    high      = [w for w in weak_areas if 5.0 <= w.gap_score < 7.0]
    medium    = [w for w in weak_areas if 3.0 <= w.gap_score < 5.0]
    anomalies = [w for w in weak_areas if w.is_anomaly]

    # Priority order = anomalies first, then sorted by gap + ca_pressure
    def priority_key(w: WeakArea) -> float:
        return w.gap_score * 1.0 + (w.ca_pressure * 0.5) + (10.0 if w.is_anomaly else 0.0)

    priority_order = [
        w.topic_name
        for w in sorted(weak_areas, key=priority_key, reverse=True)[:10]
    ]

    # Persist updated weakness scores to DB
    await _persist_weakness_scores(db, weak_areas)

    report = WeaknessReport(
        critical=critical[:5],
        high=high[:5],
        medium=medium[:5],
        anomalies=anomalies[:10],
        priority_order=priority_order,
    )

    logger.info(
        f"✅ Weakness report: "
        f"{len(critical)} critical | {len(high)} high | "
        f"{len(medium)} medium | {len(anomalies)} anomalies"
    )
    return report


async def _persist_weakness_scores(
    db: AsyncSession,
    weak_areas: list[WeakArea],
) -> None:
    """
    Writes computed gap scores back to UserTopicStat table
    so the analytics endpoint can read them without recomputing.
    """
    stats_result = await db.execute(select(UserTopicStat))
    stats_map = {s.topic_id: s for s in stats_result.scalars().all()}

    for w in weak_areas:
        stat = stats_map.get(w.topic_id)
        if not stat:
            stat = UserTopicStat(topic_id=w.topic_id)
            db.add(stat)

        stat.weakness_score  = w.gap_score
        stat.is_anomaly      = w.is_anomaly
        stat.anomaly_reason  = w.reason

        if w.gap_score >= 7.0:
            stat.weakness_level = WeaknessLevel.CRITICAL
        elif w.gap_score >= 5.0:
            stat.weakness_level = WeaknessLevel.HIGH
        elif w.gap_score >= 3.0:
            stat.weakness_level = WeaknessLevel.MEDIUM
        elif w.gap_score >= 1.0:
            stat.weakness_level = WeaknessLevel.LOW
        else:
            stat.weakness_level = WeaknessLevel.STRONG

    await db.commit()


# ── Conversation Coverage Updater ─────────────────────────────────────────────

async def update_coverage_from_conversation(
    db: AsyncSession,
    topic_ids: list[int],
    quality_score: float = 0.5,
) -> None:
    """
    Called after each conversation turn to update coverage scores.

    Args:
        topic_ids:     topics that were discussed in this turn
        quality_score: 0.0–1.0 estimated depth of engagement
                       (0.3 = brief mention, 0.7 = good discussion, 1.0 = deep dive)
    """
    if not topic_ids:
        return

    stats_result = await db.execute(
        select(UserTopicStat).where(UserTopicStat.topic_id.in_(topic_ids))
    )
    existing = {s.topic_id: s for s in stats_result.scalars().all()}

    for topic_id in topic_ids:
        stat = existing.get(topic_id)
        if not stat:
            stat = UserTopicStat(
                topic_id=topic_id,
                coverage_score=0.0,
                revision_count=0,
                question_count=0,
            )
            db.add(stat)

        # Increment coverage (capped at 10.0)
        stat.coverage_score  = min(10.0, stat.coverage_score + quality_score)
        stat.question_count  = (stat.question_count or 0) + 1
        stat.revision_count  = (stat.revision_count or 0) + 1
        stat.last_revised    = datetime.utcnow()

    await db.commit()


# ── Micro-tag Confidence Updater ──────────────────────────────────────────────

async def update_microtag_confidence(
    db: AsyncSession,
    micro_tag_ids: list[int],
    confidence_delta: float = 0.1,
) -> None:
    """
    Updates per-concept confidence scores after a conversation turn.

    confidence_delta > 0 means the concept was engaged with positively.
    confidence_delta < 0 means the student expressed confusion.
    """
    if not micro_tag_ids:
        return

    stats_result = await db.execute(
        select(UserMicroTagStat)
        .where(UserMicroTagStat.micro_tag_id.in_(micro_tag_ids))
    )
    existing = {s.micro_tag_id: s for s in stats_result.scalars().all()}

    for mt_id in micro_tag_ids:
        stat = existing.get(mt_id)
        if not stat:
            stat = UserMicroTagStat(
                micro_tag_id=mt_id,
                confidence_level=0.5,
                never_touched=False,
            )
            db.add(stat)

        stat.confidence_level = max(0.0, min(1.0, stat.confidence_level + confidence_delta))
        stat.times_asked      = (stat.times_asked or 0) + 1
        stat.never_touched    = False
        stat.last_interaction = datetime.utcnow()
        stat.weak_flag        = stat.confidence_level < 0.4

    await db.commit()
