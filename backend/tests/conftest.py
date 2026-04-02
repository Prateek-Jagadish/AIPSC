"""
tests/conftest.py
─────────────────
Shared pytest fixtures for the UPSC Intelligence System test suite.

Provides:
    - In-memory async SQLAlchemy test database (SQLite)
    - FastAPI test client with DB dependency override
    - Sample data factories for topics, documents, chunks, etc.

Note: We use SQLite for unit tests to avoid requiring PostgreSQL.
      Integration tests that need pgvector should use a real PostgreSQL.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

# Patch pgvector BEFORE importing models
# SQLite doesn't support vector columns, so we replace them with Text
import sqlalchemy as sa
original_column = sa.Column

def patched_column(*args, **kwargs):
    """Replace Vector(3072) columns with Text for SQLite compatibility."""
    new_args = []
    for arg in args:
        if hasattr(arg, '__class__') and arg.__class__.__name__ == 'Vector':
            new_args.append(sa.Text())
        else:
            new_args.append(arg)
    return original_column(*new_args, **kwargs)

# We'll mock the vector import at module level
from unittest.mock import MagicMock
vector_mock = MagicMock()
vector_mock.Vector = lambda dim: sa.Text()

import sys
sys.modules.setdefault('pgvector', vector_mock)
sys.modules.setdefault('pgvector.sqlalchemy', vector_mock)

from app.core.database import Base
from app.core.config import settings


# ── Test Database Engine ──────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_upsc.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestSessionFactory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Provide a clean database session for each test."""
    async with TestSessionFactory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """
    FastAPI test client with the database dependency overridden
    to use the test database session.
    """
    from app.main import app
    from app.core.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Sample Data Factories ─────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def sample_topic(db_session):
    """Create a sample topic for tests."""
    from app.models.topic import Topic, GSPaper
    topic = Topic(
        name="Indian Polity",
        paper=GSPaper.GS2,
        description="Constitution, governance, and political system",
        priority_score=8.5,
    )
    db_session.add(topic)
    await db_session.commit()
    await db_session.refresh(topic)
    return topic


@pytest_asyncio.fixture
async def sample_subtopic(db_session, sample_topic):
    """Create a sample subtopic."""
    from app.models.topic import Subtopic
    subtopic = Subtopic(
        topic_id=sample_topic.id,
        name="Federalism",
        description="Centre-state relations",
        priority_score=8.0,
    )
    db_session.add(subtopic)
    await db_session.commit()
    await db_session.refresh(subtopic)
    return subtopic


@pytest_asyncio.fixture
async def sample_micro_tag(db_session, sample_subtopic):
    """Create a sample micro tag."""
    from app.models.topic import MicroTag
    micro_tag = MicroTag(
        subtopic_id=sample_subtopic.id,
        name="GST Council",
        description="Goods and Services Tax Council",
        pyq_weight=7.5,
    )
    db_session.add(micro_tag)
    await db_session.commit()
    await db_session.refresh(micro_tag)
    return micro_tag


@pytest_asyncio.fixture
async def sample_document(db_session):
    """Create a sample document record."""
    from app.models.document import Document, DocumentType, DocumentStatus
    doc = Document(
        title="Test NCERT Class 11 Polity",
        source_type=DocumentType.NCERT,
        status=DocumentStatus.UPLOADED,
        file_path="/tmp/test_polity.pdf",
        file_size_kb=1024.0,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest_asyncio.fixture
async def sample_chunk(db_session, sample_document, sample_topic):
    """Create a sample text chunk."""
    from app.models.document import Chunk
    chunk = Chunk(
        document_id=sample_document.id,
        text="Federalism in India is quasi-federal. The Constitution provides for a strong centre.",
        page_number=1,
        chunk_index=0,
        topic_id=sample_topic.id,
        token_count=15,
    )
    db_session.add(chunk)
    await db_session.commit()
    await db_session.refresh(chunk)
    return chunk


@pytest_asyncio.fixture
async def sample_conversation(db_session):
    """Create a sample conversation session."""
    from app.models.conversation import Conversation
    conv = Conversation(
        turn_count=0,
    )
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv
