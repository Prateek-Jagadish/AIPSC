"""
models/current_affair.py
────────────────────────
Daily newspaper articles filtered and structured for UPSC.

Each record represents one UPSC-relevant article from a newspaper.
The system filters raw articles, summarizes them, maps them to the
topic taxonomy, and generates probable question angles.

This table grows daily as you upload newspapers.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Text,
    ForeignKey, Enum as SAEnum, DateTime, Boolean, Date
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import enum

from app.core.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class RelevanceLevel(str, enum.Enum):
    HIGH    = "High"
    MEDIUM  = "Medium"
    LOW     = "Low"


class ExamRelevance(str, enum.Enum):
    MAINS_ONLY    = "Mains Only"
    PRELIMS_ONLY  = "Prelims Only"
    BOTH          = "Both"
    NONE          = "None"


# ── Current Affair ────────────────────────────────────────────────────────────

class CurrentAffair(Base):
    """
    One UPSC-relevant article extracted from a daily newspaper.

    Workflow:
        1. Newspaper PDF uploaded
        2. Articles extracted
        3. AI filters UPSC-relevant ones (this table gets populated)
        4. Each article is summarized, tagged, and embedded
        5. Probable question angle is generated

    Key design: date is always stored — so the system knows
    when each piece of information entered your knowledge base.
    """
    __tablename__ = "current_affairs"

    id                    = Column(Integer, primary_key=True, index=True)

    # ── Source ─────────────────────────────────────────────────────────────
    newspaper_date        = Column(Date, nullable=False, index=True)     # date of newspaper
    publication           = Column(String(200), nullable=True)           # e.g. "The Hindu"
    source_document_id    = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    page_number           = Column(Integer, nullable=True)

    # ── Content ────────────────────────────────────────────────────────────
    headline              = Column(String(500), nullable=False)
    raw_text              = Column(Text, nullable=True)                  # original article
    summary               = Column(Text, nullable=False)                 # AI 3–5 line summary
    key_facts             = Column(Text, nullable=True)                  # bullet facts for prelims
    upsc_angle            = Column(Text, nullable=True)                  # why UPSC cares

    # ── Topic Mapping ──────────────────────────────────────────────────────
    topic_id              = Column(Integer, ForeignKey("topics.id"),     nullable=True, index=True)
    subtopic_id           = Column(Integer, ForeignKey("subtopics.id"),  nullable=True, index=True)
    micro_tag_id          = Column(Integer, ForeignKey("micro_tags.id"), nullable=True, index=True)

    # ── UPSC Relevance ─────────────────────────────────────────────────────
    relevance_score       = Column(Float, default=5.0)                  # 1–10 AI-assigned
    relevance_level       = Column(SAEnum(RelevanceLevel), default=RelevanceLevel.MEDIUM)
    exam_relevance        = Column(SAEnum(ExamRelevance),  default=ExamRelevance.BOTH)

    # ── Question Intelligence ──────────────────────────────────────────────
    probable_question     = Column(Text, nullable=True)                  # probable UPSC question
    mains_dimensions      = Column(Text, nullable=True)                  # angles for mains answer
    prelims_facts         = Column(Text, nullable=True)                  # facts for prelims
    static_linkage        = Column(Text, nullable=True)                  # linked static topic

    # ── Visual ─────────────────────────────────────────────────────────────
    has_map_reference     = Column(Boolean, default=False)

    # ── Embedding ──────────────────────────────────────────────────────────
    embedding             = Column(Vector(3072), nullable=True)

    created_at            = Column(DateTime(timezone=True), server_default=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    topic                 = relationship("Topic",    back_populates="current_affairs")
    subtopic              = relationship("Subtopic", back_populates="current_affairs")
    micro_tag             = relationship("MicroTag", back_populates="current_affairs")

    def __repr__(self):
        return (
            f"<CurrentAffair id={self.id} date={self.newspaper_date} "
            f"headline='{self.headline[:50]}...'>"
        )
