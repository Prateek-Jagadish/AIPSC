"""
tests/test_models.py
────────────────────
Tests for SQLAlchemy models — validates that all models
can be created, relationships work, and enums are correct.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select


# ══════════════════════════════════════════════════════════════════════════════
# Topic Taxonomy Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_topic(db_session):
    """Test that a topic can be created with all required fields."""
    from app.models.topic import Topic, GSPaper

    topic = Topic(
        name="Indian Economy",
        paper=GSPaper.GS3,
        description="Economic development and planning",
        priority_score=7.5,
    )
    db_session.add(topic)
    await db_session.commit()
    await db_session.refresh(topic)

    assert topic.id is not None
    assert topic.name == "Indian Economy"
    assert topic.paper == GSPaper.GS3
    assert topic.priority_score == 7.5


@pytest.mark.asyncio
async def test_topic_subtopic_relationship(db_session, sample_topic):
    """Test Topic → Subtopic hierarchy."""
    from app.models.topic import Subtopic

    sub1 = Subtopic(topic_id=sample_topic.id, name="Fundamental Rights")
    sub2 = Subtopic(topic_id=sample_topic.id, name="Directive Principles")
    db_session.add_all([sub1, sub2])
    await db_session.commit()

    result = await db_session.execute(
        select(Subtopic).where(Subtopic.topic_id == sample_topic.id)
    )
    subtopics = result.scalars().all()
    assert len(subtopics) == 2
    names = {s.name for s in subtopics}
    assert "Fundamental Rights" in names
    assert "Directive Principles" in names


@pytest.mark.asyncio
async def test_subtopic_microtag_relationship(db_session, sample_subtopic):
    """Test Subtopic → MicroTag hierarchy."""
    from app.models.topic import MicroTag

    mt1 = MicroTag(subtopic_id=sample_subtopic.id, name="Article 370")
    mt2 = MicroTag(subtopic_id=sample_subtopic.id, name="Inter-State Council")
    db_session.add_all([mt1, mt2])
    await db_session.commit()

    result = await db_session.execute(
        select(MicroTag).where(MicroTag.subtopic_id == sample_subtopic.id)
    )
    tags = result.scalars().all()
    assert len(tags) == 2


# ══════════════════════════════════════════════════════════════════════════════
# Document + Chunk Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_document(db_session):
    """Test that a document can be created with proper defaults."""
    from app.models.document import Document, DocumentType, DocumentStatus

    doc = Document(
        title="Test PDF",
        source_type=DocumentType.NOTES,
        status=DocumentStatus.UPLOADED,
        file_path="/storage/test.pdf",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    assert doc.id is not None
    assert doc.status == DocumentStatus.UPLOADED
    assert doc.source_type == DocumentType.NOTES
    assert doc.chunk_count == 0


@pytest.mark.asyncio
async def test_document_chunk_relationship(db_session, sample_document):
    """Test Document → Chunk cascade."""
    from app.models.document import Chunk

    chunk = Chunk(
        document_id=sample_document.id,
        text="Test chunk content about Indian constitution.",
        page_number=1,
        chunk_index=0,
    )
    db_session.add(chunk)
    await db_session.commit()

    result = await db_session.execute(
        select(Chunk).where(Chunk.document_id == sample_document.id)
    )
    chunks = result.scalars().all()
    assert len(chunks) == 1
    assert chunks[0].text.startswith("Test chunk content")


@pytest.mark.asyncio
async def test_chunk_topic_tagging(db_session, sample_document, sample_topic, sample_subtopic, sample_micro_tag):
    """Test that a chunk can be tagged with topic/subtopic/micro_tag."""
    from app.models.document import Chunk

    chunk = Chunk(
        document_id=sample_document.id,
        text="The GST Council decides on tax rates.",
        topic_id=sample_topic.id,
        subtopic_id=sample_subtopic.id,
        micro_tag_id=sample_micro_tag.id,
        tag_confidence=0.85,
    )
    db_session.add(chunk)
    await db_session.commit()
    await db_session.refresh(chunk)

    assert chunk.topic_id == sample_topic.id
    assert chunk.subtopic_id == sample_subtopic.id
    assert chunk.micro_tag_id == sample_micro_tag.id
    assert chunk.tag_confidence == 0.85


# ══════════════════════════════════════════════════════════════════════════════
# Document Type Enum Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_document_types():
    """Test all document types are valid."""
    from app.models.document import DocumentType

    assert DocumentType.PYQ.value == "PYQ"
    assert DocumentType.NCERT.value == "NCERT"
    assert DocumentType.NEWSPAPER.value == "Newspaper"
    assert DocumentType.JSON.value == "JSON"


@pytest.mark.asyncio
async def test_document_statuses():
    """Test all document statuses."""
    from app.models.document import DocumentStatus

    statuses = [s.value for s in DocumentStatus]
    assert "Uploaded" in statuses
    assert "Processing" in statuses
    assert "Tagged" in statuses
    assert "Embedded" in statuses
    assert "Failed" in statuses


# ══════════════════════════════════════════════════════════════════════════════
# Conversation Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_conversation(db_session):
    """Test conversation session creation."""
    from app.models.conversation import Conversation

    conv = Conversation(turn_count=0)
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    assert conv.id is not None
    assert conv.turn_count == 0


@pytest.mark.asyncio
async def test_conversation_turn_creation(db_session, sample_conversation):
    """Test adding turns to a conversation."""
    from app.models.conversation import ConversationTurn

    turn = ConversationTurn(
        conversation_id=sample_conversation.id,
        turn_number=1,
        user_query="Explain federalism in India",
        assistant_reply='{"concept_explanation": "..."}',
        intent="Concept Query",
    )
    db_session.add(turn)
    await db_session.commit()
    await db_session.refresh(turn)

    assert turn.id is not None
    assert turn.conversation_id == sample_conversation.id
    assert turn.turn_number == 1
    assert "federalism" in turn.user_query.lower()


@pytest.mark.asyncio
async def test_conversation_topic_linkage(db_session, sample_conversation, sample_topic):
    """Test that conversation topics can be linked to turns (Bug 2 validation)."""
    from app.models.conversation import ConversationTurn, ConversationTopic

    turn = ConversationTurn(
        conversation_id=sample_conversation.id,
        turn_number=1,
        user_query="Explain federalism",
        assistant_reply="{}",
    )
    db_session.add(turn)
    await db_session.flush()

    # This is what Bug 2 fix enables — linking turns to topics
    ct = ConversationTopic(
        turn_id=turn.id,
        topic_id=sample_topic.id,
        confidence=0.7,
    )
    db_session.add(ct)
    await db_session.commit()

    result = await db_session.execute(
        select(ConversationTopic).where(ConversationTopic.turn_id == turn.id)
    )
    topics = result.scalars().all()
    assert len(topics) == 1
    assert topics[0].topic_id == sample_topic.id
    assert topics[0].confidence == 0.7


# ══════════════════════════════════════════════════════════════════════════════
# User Stats Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_user_topic_stat_creation(db_session, sample_topic):
    """Test user preparation stats tracking."""
    from app.models.user_stats import UserTopicStat, WeaknessLevel

    stat = UserTopicStat(
        topic_id=sample_topic.id,
        coverage_score=3.0,
        weakness_score=7.0,
        weakness_level=WeaknessLevel.HIGH,
        revision_count=2,
        question_count=5,
    )
    db_session.add(stat)
    await db_session.commit()
    await db_session.refresh(stat)

    assert stat.coverage_score == 3.0
    assert stat.weakness_score == 7.0
    assert stat.weakness_level == WeaknessLevel.HIGH
    assert stat.revision_count == 2


@pytest.mark.asyncio
async def test_anomaly_detection_flag(db_session, sample_topic):
    """Test anomaly flagging in user stats."""
    from app.models.user_stats import UserTopicStat

    stat = UserTopicStat(
        topic_id=sample_topic.id,
        coverage_score=0.0,
        weakness_score=9.0,
        is_anomaly=True,
        anomaly_reason="⚠️  Never studied — high exam weight",
    )
    db_session.add(stat)
    await db_session.commit()

    assert stat.is_anomaly is True
    assert "Never studied" in stat.anomaly_reason
