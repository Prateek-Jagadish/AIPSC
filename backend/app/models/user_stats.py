"""
models/user_stats.py
────────────────────
Tracks the user's preparation profile over time.

This is the anomaly detection + weakness engine layer.
It answers:
    - "Which topics have you never discussed despite high PYQ weight?"
    - "Where is your confidence score low vs. PYQ importance?"
    - "What should you revise this week?"

Tables:
    user_topic_stats    → coverage + weakness per topic
    user_microtag_stats → granular confidence per concept
    revision_logs       → history of every revision session
"""

from sqlalchemy import (
    Column, Integer, String, Float, Text,
    ForeignKey, Enum as SAEnum, DateTime, Boolean, Date
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class WeaknessLevel(str, enum.Enum):
    CRITICAL = "Critical"    # never touched, high PYQ weight
    HIGH     = "High"        # rarely touched, high PYQ weight
    MEDIUM   = "Medium"      # some coverage, needs attention
    LOW      = "Low"         # well covered
    STRONG   = "Strong"      # thoroughly revised


class RevisionType(str, enum.Enum):
    DAILY   = "Daily"
    WEEKLY  = "Weekly"
    MONTHLY = "Monthly"
    ADHOC   = "Adhoc"        # user asked for a specific topic


# ── User Topic Stats ───────────────────────────────────────────────────────────

class UserTopicStat(Base):
    """
    Aggregate preparation score per topic.

    Updated every time a conversation touches this topic.

    coverage_score: 0–10 (how much you've studied this topic)
    weakness_score: 0–10 (10 = very weak, 0 = very strong)
        computed as: pyq_weight – coverage_score (clamped 0–10)
    """
    __tablename__ = "user_topic_stats"

    id                  = Column(Integer, primary_key=True, index=True)
    topic_id            = Column(Integer, ForeignKey("topics.id"), nullable=False, unique=True, index=True)

    # ── Scores ─────────────────────────────────────────────────────────────
    coverage_score      = Column(Float, default=0.0)      # 0–10 (how much studied)
    revision_count      = Column(Integer, default=0)
    question_count      = Column(Integer, default=0)      # times asked about this topic
    last_revised        = Column(DateTime(timezone=True), nullable=True)
    weakness_score      = Column(Float, default=5.0)      # 0–10 (10 = critical gap)
    weakness_level      = Column(SAEnum(WeaknessLevel), default=WeaknessLevel.MEDIUM)

    # ── Anomaly Flag ───────────────────────────────────────────────────────
    is_anomaly          = Column(Boolean, default=False)  # high PYQ weight, zero coverage
    anomaly_reason      = Column(Text, nullable=True)     # e.g. "Never discussed. PYQ weight: 9.0"

    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    topic               = relationship("Topic")

    def __repr__(self):
        return (
            f"<UserTopicStat topic_id={self.topic_id} "
            f"coverage={self.coverage_score} weakness={self.weakness_score}>"
        )


# ── User Micro Tag Stats ───────────────────────────────────────────────────────

class UserMicroTagStat(Base):
    """
    Granular confidence score per concept (micro_tag).

    This is the finest resolution the system tracks.
    Enables concept-level weakness detection.

    Example:
        MicroTag: "GST Council"  → confidence: 0.2, times_asked: 1, weak_flag: True
        MicroTag: "Article 356"  → confidence: 0.8, times_asked: 5, weak_flag: False
    """
    __tablename__ = "user_microtag_stats"

    id                  = Column(Integer, primary_key=True, index=True)
    micro_tag_id        = Column(Integer, ForeignKey("micro_tags.id"), nullable=False, unique=True, index=True)

    # ── Engagement Metrics ─────────────────────────────────────────────────
    confidence_level    = Column(Float, default=0.5)       # 0.0 – 1.0
    times_asked         = Column(Integer, default=0)
    times_revised       = Column(Integer, default=0)
    times_answered_well = Column(Integer, default=0)       # AI estimated quality

    # ── Flags ──────────────────────────────────────────────────────────────
    weak_flag           = Column(Boolean, default=False)   # needs attention
    never_touched       = Column(Boolean, default=True)    # default True → flipped when first asked
    last_interaction    = Column(DateTime(timezone=True), nullable=True)

    # ── Revision Due ───────────────────────────────────────────────────────
    next_revision_due   = Column(Date, nullable=True)      # spaced repetition hint

    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    micro_tag           = relationship("MicroTag", back_populates="user_stats")

    def __repr__(self):
        return (
            f"<UserMicroTagStat micro_tag_id={self.micro_tag_id} "
            f"confidence={self.confidence_level} weak={self.weak_flag}>"
        )


# ── Revision Log ──────────────────────────────────────────────────────────────

class RevisionLog(Base):
    """
    Records every revision session generated by the system.
    Used to track history and improve future revision plans.
    """
    __tablename__ = "revision_logs"

    id              = Column(Integer, primary_key=True, index=True)
    revision_type   = Column(SAEnum(RevisionType), nullable=False)
    period_label    = Column(String(100), nullable=True)   # e.g. "Week 12, 2025"

    # ── Content ────────────────────────────────────────────────────────────
    topics_covered  = Column(Text, nullable=True)          # JSON list of topic IDs
    weak_areas      = Column(Text, nullable=True)          # JSON list
    ca_highlights   = Column(Text, nullable=True)          # current affairs in this period
    cheat_sheet     = Column(Text, nullable=True)          # full generated cheat sheet text

    # ── Feedback ───────────────────────────────────────────────────────────
    user_rating     = Column(Integer, nullable=True)       # 1–5 (if user rates)
    user_notes      = Column(Text, nullable=True)

    generated_at    = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<RevisionLog id={self.id} type={self.revision_type} period='{self.period_label}'>"
