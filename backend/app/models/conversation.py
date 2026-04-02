"""
models/conversation.py
──────────────────────
Stores every interaction between the user and the assistant.

This is what enables:
    - "Which topics am I lagging in?"
    - "Give me my weekly revision cheat sheet"
    - Anomaly detection (high-PYQ topics you never discuss)
    - Personalized study pattern analysis

Tables:
    conversations        → one record per chat session
    conversation_turns   → individual messages within a session
    conversation_topics  → topics extracted from each turn
"""

from sqlalchemy import (
    Column, Integer, String, Float, Text,
    ForeignKey, Enum as SAEnum, DateTime, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class QueryIntent(str, enum.Enum):
    CONCEPT_QUERY      = "Concept Query"        # explain a topic
    PYQ_SEARCH         = "PYQ Search"           # find past questions
    CA_LINK            = "CA Link"              # link current affairs
    ANSWER_WRITING     = "Answer Writing"       # generate answer
    WEAKNESS_CHECK     = "Weakness Check"       # where am I weak?
    REVISION           = "Revision"             # give revision plan
    MAP_QUERY          = "Map Query"            # map/diagram request
    TREND_ANALYSIS     = "Trend Analysis"       # PYQ pattern analysis
    GENERAL            = "General"


class EngagementDepth(str, enum.Enum):
    SHALLOW   = "Shallow"    # one-line question, quick answer
    MEDIUM    = "Medium"     # multi-turn discussion
    DEEP      = "Deep"       # full answer writing + follow-ups


# ── Conversation Session ──────────────────────────────────────────────────────

class Conversation(Base):
    """
    One complete study session (could be multiple questions).
    Groups conversation turns together.
    """
    __tablename__ = "conversations"

    id              = Column(Integer, primary_key=True, index=True)
    session_date    = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    session_title   = Column(String(300), nullable=True)    # auto-generated from first query
    turn_count      = Column(Integer, default=0)

    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    ended_at        = Column(DateTime(timezone=True), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    turns           = relationship("ConversationTurn", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation id={self.id} date={self.session_date} turns={self.turn_count}>"


# ── Conversation Turn ─────────────────────────────────────────────────────────

class ConversationTurn(Base):
    """
    A single question-answer exchange within a session.

    user_query      → what Prateek asked
    assistant_reply → what the system answered
    intent          → classified purpose of the query
    topics_covered  → which topics this turn touched (FK to ConversationTopic)
    """
    __tablename__ = "conversation_turns"

    id                  = Column(Integer, primary_key=True, index=True)
    conversation_id     = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_number         = Column(Integer, nullable=False)

    # ── Content ────────────────────────────────────────────────────────────
    user_query          = Column(Text, nullable=False)
    assistant_reply     = Column(Text, nullable=False)

    # ── Intelligence ───────────────────────────────────────────────────────
    intent              = Column(SAEnum(QueryIntent), default=QueryIntent.GENERAL)
    engagement_depth    = Column(SAEnum(EngagementDepth), default=EngagementDepth.MEDIUM)
    follow_up_suggested = Column(Boolean, default=False)
    unresolved_doubt    = Column(Boolean, default=False)
    unresolved_note     = Column(Text, nullable=True)    # what was left unclear

    # ── System Notes ───────────────────────────────────────────────────────
    # What the system concluded from this turn (used for revision + weakness)
    system_conclusion   = Column(Text, nullable=True)
    urgency_score       = Column(Float, default=5.0)     # 1–10

    created_at          = Column(DateTime(timezone=True), server_default=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    conversation        = relationship("Conversation",   back_populates="turns")
    topics_covered      = relationship("ConversationTopic", back_populates="turn", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Turn id={self.id} conv_id={self.conversation_id} turn={self.turn_number}>"


# ── Conversation Topic ─────────────────────────────────────────────────────────

class ConversationTopic(Base):
    """
    Records which topic/subtopic/micro_tag was discussed in a turn.
    This is the bridge between conversations and the topic taxonomy.

    Powers:
        - weakness detection (high PYQ topics never appearing here)
        - coverage scoring
        - revision cheat sheet generation
    """
    __tablename__ = "conversation_topics"

    id              = Column(Integer, primary_key=True, index=True)
    turn_id         = Column(Integer, ForeignKey("conversation_turns.id", ondelete="CASCADE"), nullable=False, index=True)

    # ── Topic Anchor ───────────────────────────────────────────────────────
    topic_id        = Column(Integer, ForeignKey("topics.id"),     nullable=True, index=True)
    subtopic_id     = Column(Integer, ForeignKey("subtopics.id"),  nullable=True, index=True)
    micro_tag_id    = Column(Integer, ForeignKey("micro_tags.id"), nullable=True, index=True)

    # ── Engagement Quality ─────────────────────────────────────────────────
    confidence      = Column(Float, default=0.5)          # how well understood (AI estimate)
    was_revised     = Column(Boolean, default=False)
    action_taken    = Column(Boolean, default=False)       # e.g. "noted", "practiced"

    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    # ── Relationships ──────────────────────────────────────────────────────
    turn            = relationship("ConversationTurn", back_populates="topics_covered")

    def __repr__(self):
        return (
            f"<ConvTopic turn_id={self.turn_id} "
            f"topic_id={self.topic_id} micro_tag_id={self.micro_tag_id}>"
        )
