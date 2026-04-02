"""
core/database.py
────────────────
Async database engine, session factory, and base model setup.
Includes pgvector extension initialization.

Usage:
    from app.core.database import get_db, Base

    # In a FastAPI route:
    async def my_route(db: AsyncSession = Depends(get_db)):
        ...

    # All SQLAlchemy models inherit from Base:
    class MyModel(Base):
        ...
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from loguru import logger
from typing import AsyncGenerator

from app.core.config import settings


# ── Engine ────────────────────────────────────────────────────────────────────

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,        # log all SQL in dev
    pool_pre_ping=True,         # auto-reconnect on stale connections
    pool_size=10,               # connection pool size
    max_overflow=20,            # extra connections beyond pool_size
)


# ── Session Factory ───────────────────────────────────────────────────────────

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,     # keep ORM objects usable after commit
    autoflush=False,
    autocommit=False,
)


# ── Base Model ────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """
    All SQLAlchemy models in this project inherit from this class.
    Provides a shared metadata registry used by Alembic migrations.
    """
    pass


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session per request.
    The session is automatically closed when the request ends.

    Usage in routes:
        async def route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Startup Initialization ────────────────────────────────────────────────────

async def init_db() -> None:
    """
    Called once at application startup.
    - Enables the pgvector extension (needed for vector columns).
    - Creates all tables if they don't exist.
    """
    async with engine.begin() as conn:
        # Enable pgvector extension in PostgreSQL
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("✅ pgvector extension enabled")

        # Create all tables defined in models (imported via Base)
        # Note: In production, use Alembic migrations instead.
        # This is useful for initial setup and tests.
        await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created / verified")


async def close_db() -> None:
    """
    Called at application shutdown — cleanly disposes the engine.
    """
    await engine.dispose()
    logger.info("✅ Database connection pool closed")
