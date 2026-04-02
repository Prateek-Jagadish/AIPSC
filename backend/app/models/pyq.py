"""
models/pyq.py
─────────────
Previous Year Questions — the pattern backbone of the system.
Used for PYQ trend analysis, probable question generation,
and weakness detection.

Source: PYQ PDFs (2016–2025) + JSON file with model answers
"""

from sqlalchemy import (
    Column, Integer, String, Float, Text,
    ForeignKey, Enum as SAEnum, DateTime, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import enum

from app.core.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class ExamType(str, enum.Enum):
    MAINS   = "Mains"
    PRELIMS = "Prelims"


class GSSPaper(str, enum.Enum):
    GS1          = "GS1"
    GS2          = "GS2"
    GS3          = "GS3"
    GS4          = "GS4"
    ESSAY        = "Essay"
    PRELIMS_GS1  = "Prelims_GS1"
    PRELIMS_GS2  = "Prelims_GS2"   # CSAT


class CommandWord(str, enum.Enum):
    DISCUSS    = "Discuss"
    ANALYZE    = "Analyze"
    EXAMINE    = "Examine"
    EVALUATE   = "Evaluate"
    COMMENT    = "Comment"
    CRITICALLY = "Critically Examine"
    EXPLAIN    = "Explain"
    HIGHLIGHT  = "Highlight"
    ENUMERATE  = "Enumerate"
    OTHER      = "Other"


class QuestionType(str, enum.Enum):
    CONCEPTUAL    = "Conceptual"
    ANALYTICAL    = "Analytical"
    CASE_STUDY    = "Case Study"
    FACTUAL       = "Factual"
    OPINION       = "Opinion"
    STATEMENT     = "Statement Based"    # "Which of the following..." (Prelims)
    MCQ           = "MCQ"


class Difficulty(str, enum.Enum):
    EASY   = "Easy"
    MEDIUM = "Medium"
    HARD   = "Hard"


# ── PYQ ───────────────────────────────────────────────────────────────────────

class PYQ(Base):
    """
    A single previous year question from Mains or Prelims.

    For Mains:
        - Full question text
        - Model answer (from JSON)
        - Word limit (150 / 250 words)
        - Marks (10 / 15)

    For Prelims:
        - Question stem + 4 options
        - Correct answer
        - Option analysis
    """
    __tablename__ = "pyqs"

    id              = Column(Integer, primary_key=True, index=True)

    # ── Question Identity ──────────────────────────────────────────────────
    year            = Column(Integer, nullable=False, index=True)   # 2016 – 2025
    exam_type       = Column(SAEnum(ExamType),   nullable=False, index=True)
    paper           = Column(SAEnum(GSSPaper),   nullable=False, index=True)
    question_number = Column(Integer, nullable=True)
    marks           = Column(Integer, nullable=True)                 # 10 / 15 (Mains)
    word_limit      = Column(Integer, nullable=True)                 # 150 / 250 (Mains)

    # ── Content ────────────────────────────────────────────────────────────
    question_text   = Column(Text, nullable=False)

    # For Prelims MCQs
    option_a        = Column(Text, nullable=True)
    option_b        = Column(Text, nullable=True)
    option_c        = Column(Text, nullable=True)
    option_d        = Column(Text, nullable=True)
    correct_option  = Column(String(1), nullable=True)              # 'A', 'B', 'C', 'D'
    option_analysis = Column(Text, nullable=True)                   # why other options wrong

    # ── Model Answer (Mains) ───────────────────────────────────────────────
    model_answer    = Column(Text, nullable=True)                   # from JSON
    answer_intro    = Column(Text, nullable=True)
    answer_body     = Column(Text, nullable=True)
    answer_conclusion = Column(Text, nullable=True)
    diagram_suggested = Column(Boolean, default=False)

    # ── Classification ─────────────────────────────────────────────────────
    topic_id        = Column(Integer, ForeignKey("topics.id"),     nullable=True, index=True)
    subtopic_id     = Column(Integer, ForeignKey("subtopics.id"),  nullable=True, index=True)
    micro_tag_id    = Column(Integer, ForeignKey("micro_tags.id"), nullable=True, index=True)

    command_word    = Column(SAEnum(CommandWord), default=CommandWord.OTHER)
    question_type   = Column(SAEnum(QuestionType), default=QuestionType.CONCEPTUAL)
    difficulty      = Column(SAEnum(Difficulty), default=Difficulty.MEDIUM)

    # ── Embedding ──────────────────────────────────────────────────────────
    embedding       = Column(Vector(3072), nullable=True)

    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    topic           = relationship("Topic",    back_populates="pyqs")
    subtopic        = relationship("Subtopic", back_populates="pyqs")
    micro_tag       = relationship("MicroTag", back_populates="pyqs")

    def __repr__(self):
        return (
            f"<PYQ id={self.id} year={self.year} "
            f"paper={self.paper} type={self.exam_type}>"
        )
