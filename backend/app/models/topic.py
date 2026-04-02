"""
models/topic.py
───────────────
The BRAIN of the system.
Every piece of data — PYQs, chunks, current affairs, images, conversations —
is anchored to this topic taxonomy.

Tables:
    topics       → GS Paper → Subject (e.g. GS2 → Polity)
    subtopics    → Topics → Subtopic (e.g. Polity → Federalism)
    micro_tags   → Subtopics → Concept (e.g. Federalism → GST Council)
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text,
    ForeignKey, Enum as SAEnum, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class GSPaper(str, enum.Enum):
    GS1 = "GS1"
    GS2 = "GS2"
    GS3 = "GS3"
    GS4 = "GS4"
    ESSAY = "Essay"
    PRELIMS_GS1 = "Prelims_GS1"
    PRELIMS_GS2 = "Prelims_GS2"  # CSAT


class ExamFocus(str, enum.Enum):
    MAINS = "Mains"
    PRELIMS = "Prelims"
    BOTH = "Both"


class CurrentAffairsSensitivity(str, enum.Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class DiagramType(str, enum.Enum):
    FLOWCHART = "Flowchart"
    MAP = "Map"
    TABLE = "Table"
    GRAPH = "Graph"
    NONE = "None"


# ── Topics ────────────────────────────────────────────────────────────────────

class Topic(Base):
    """
    Top-level subject grouping under a GS paper.
    Example: GS2 → Polity
             GS3 → Economy
             GS1 → Ancient History
    """
    __tablename__ = "topics"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(200), nullable=False, unique=True)   # e.g. "Polity"
    paper         = Column(SAEnum(GSPaper), nullable=False)            # e.g. GS2
    description   = Column(Text, nullable=True)
    priority_score = Column(Float, default=5.0)                        # 1–10 scale
    exam_focus    = Column(SAEnum(ExamFocus), default=ExamFocus.BOTH)

    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    subtopics     = relationship("Subtopic",    back_populates="topic",    cascade="all, delete-orphan")
    chunks        = relationship("Chunk",       back_populates="topic")
    pyqs          = relationship("PYQ",         back_populates="topic")
    current_affairs = relationship("CurrentAffair", back_populates="topic")
    visual_assets = relationship("VisualAsset", back_populates="topic")

    def __repr__(self):
        return f"<Topic id={self.id} name='{self.name}' paper={self.paper}>"


# ── Subtopics ─────────────────────────────────────────────────────────────────

class Subtopic(Base):
    """
    Mid-level grouping within a topic.
    Example: Polity → Federalism
             Economy → Demand & Supply
             History → Indus Valley Civilization
    """
    __tablename__ = "subtopics"

    id            = Column(Integer, primary_key=True, index=True)
    topic_id      = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    name          = Column(String(300), nullable=False)
    description   = Column(Text, nullable=True)
    priority_score = Column(Float, default=5.0)                         # 1–10 scale
    ca_sensitivity = Column(SAEnum(CurrentAffairsSensitivity), default=CurrentAffairsSensitivity.MEDIUM)
    exam_focus    = Column(SAEnum(ExamFocus), default=ExamFocus.BOTH)

    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    topic         = relationship("Topic",       back_populates="subtopics")
    micro_tags    = relationship("MicroTag",    back_populates="subtopic", cascade="all, delete-orphan")
    chunks        = relationship("Chunk",       back_populates="subtopic")
    pyqs          = relationship("PYQ",         back_populates="subtopic")
    current_affairs = relationship("CurrentAffair", back_populates="subtopic")
    visual_assets = relationship("VisualAsset", back_populates="subtopic")

    def __repr__(self):
        return f"<Subtopic id={self.id} name='{self.name}' topic_id={self.topic_id}>"


# ── Micro Tags ────────────────────────────────────────────────────────────────

class MicroTag(Base):
    """
    Concept-level tags — the most precise unit in the taxonomy.
    This is what enables UPSC-level precision in retrieval.

    Example: Federalism → GST Council
             Federalism → Article 356 misuse
             IVC        → Town planning
             Demand     → Government intervention (tax, subsidy, price control)
    """
    __tablename__ = "micro_tags"

    id                   = Column(Integer, primary_key=True, index=True)
    subtopic_id          = Column(Integer, ForeignKey("subtopics.id", ondelete="CASCADE"), nullable=False, index=True)
    name                 = Column(String(300), nullable=False)
    description          = Column(Text, nullable=True)

    # ── UPSC Intelligence Metadata ─────────────────────────────────────────
    pyq_weight           = Column(Float, default=5.0)        # How often in PYQs (1–10)
    current_affairs_weight = Column(Float, default=5.0)      # CA linkage strength (1–10)
    diagram_relevant     = Column(Boolean, default=False)    # Does this need a diagram?
    diagram_type         = Column(SAEnum(DiagramType), default=DiagramType.NONE)
    exam_focus           = Column(SAEnum(ExamFocus), default=ExamFocus.BOTH)

    # ── Answer Writing Hints ───────────────────────────────────────────────
    answer_type          = Column(String(100), nullable=True)   # e.g. "Analytical + Current Affairs"
    common_command_words = Column(String(200), nullable=True)   # e.g. "Discuss, Analyze, Evaluate"

    created_at           = Column(DateTime(timezone=True), server_default=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    subtopic             = relationship("Subtopic",   back_populates="micro_tags")
    chunks               = relationship("Chunk",      back_populates="micro_tag")
    pyqs                 = relationship("PYQ",        back_populates="micro_tag")
    current_affairs      = relationship("CurrentAffair", back_populates="micro_tag")
    visual_assets        = relationship("VisualAsset",   back_populates="micro_tag")
    user_stats           = relationship("UserMicroTagStat", back_populates="micro_tag")

    def __repr__(self):
        return f"<MicroTag id={self.id} name='{self.name}' subtopic_id={self.subtopic_id}>"
