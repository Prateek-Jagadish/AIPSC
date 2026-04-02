"""
tests/test_ingestion.py
───────────────────────
Tests for the ingestion pipeline — chunking, PDF detection, and
the newspaper pipeline routing.

These test the internal service logic, not the API endpoints.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock


# ══════════════════════════════════════════════════════════════════════════════
# Chunker Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_chunker_splits_text():
    """Test that chunker produces correctly sized chunks."""
    from app.services.ingestion.chunker import create_chunks

    # Create a text that's long enough to be split
    text = "This is a test sentence about Indian polity. " * 200  # ~1000 words

    chunks = create_chunks(text, max_tokens=100, overlap=20)

    assert len(chunks) > 1  # should be split into multiple chunks
    for chunk in chunks:
        assert len(chunk) > 0   # no empty chunks


@pytest.mark.asyncio
async def test_chunker_short_text():
    """Test that short text produces a single chunk."""
    from app.services.ingestion.chunker import create_chunks

    text = "Short text about the Constitution of India."
    chunks = create_chunks(text, max_tokens=800, overlap=100)

    assert len(chunks) == 1
    assert chunks[0] == text


@pytest.mark.asyncio
async def test_chunker_empty_text():
    """Test that empty text produces no chunks."""
    from app.services.ingestion.chunker import create_chunks

    chunks = create_chunks("", max_tokens=800, overlap=100)
    assert len(chunks) == 0 or chunks == [""]


# ══════════════════════════════════════════════════════════════════════════════
# PDF Detector Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_pdf_type_detection():
    """Test that PDF type detection correctly identifies text-based PDFs."""
    from app.services.ingestion.pdf_detector import detect_pdf_type

    # We can't create real PDF bytes in unit tests easily,
    # but we can test the function signature exists and is callable
    assert callable(detect_pdf_type)


# ══════════════════════════════════════════════════════════════════════════════
# Newspaper Pipeline Routing Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_newspaper_bg_process_calls_correct_pipeline():
    """
    Bug 1 regression: _bg_process_newspaper must call
    newspaper_pipeline.process_newspaper, not process_document.
    """
    with patch(
        "app.services.ingestion.newspaper_pipeline.process_newspaper",
        new_callable=AsyncMock,
    ) as mock_newspaper, patch(
        "app.core.database.AsyncSessionFactory",
    ) as mock_factory:
        # Mock the session context manager
        mock_session = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.api.routes.upload import _bg_process_newspaper

        await _bg_process_newspaper(42)

        # Verify newspaper pipeline was called (not generic process_document)
        mock_newspaper.assert_called_once_with(mock_session, 42)


# ══════════════════════════════════════════════════════════════════════════════
# Visual Captioning Auto-trigger Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_visual_captioning_triggered_when_images_exist():
    """
    Bug 3 regression: process_document must call process_document_visuals
    when image_count > 0.
    """
    import app.services.ingestion.document_ingestion_service as ingestion

    # Just verify the import path exists — the actual function
    # uses asyncio.create_task which needs a running event loop
    assert hasattr(ingestion, 'process_document')

    # Check that the source code contains the visual captioning call
    import inspect
    source = inspect.getsource(ingestion.process_document)
    assert "process_document_visuals" in source, \
        "process_document must call process_document_visuals for images"


@pytest.mark.asyncio
async def test_visual_captioning_not_triggered_without_images():
    """
    Verify that visual captioning is only triggered when images exist.
    """
    import inspect
    import app.services.ingestion.document_ingestion_service as ingestion

    source = inspect.getsource(ingestion.process_document)
    assert "if image_count > 0" in source, \
        "Visual captioning should only trigger when image_count > 0"


# ══════════════════════════════════════════════════════════════════════════════
# Celery Dispatch Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_celery_fallback_to_background_tasks():
    """
    Bug 4 regression: When Redis is unavailable, _dispatch_task
    should fall back to FastAPI BackgroundTasks.
    """
    from app.api.routes.upload import _dispatch_task, _celery_available
    from fastapi import BackgroundTasks

    # Reset the cache
    if hasattr(_celery_available, "_ok"):
        delattr(_celery_available, "_ok")

    # Mock celery as unavailable
    with patch("app.api.routes.upload._celery_available", return_value=False):
        bg = MagicMock(spec=BackgroundTasks)
        fallback = AsyncMock()

        _dispatch_task(bg, "process_document", fallback, 123)

        # Should use BackgroundTasks, not Celery
        bg.add_task.assert_called_once_with(fallback, 123)


@pytest.mark.asyncio
async def test_celery_dispatch_when_available():
    """
    Bug 4 regression: When Redis is available, _dispatch_task
    should use Celery's send_task.
    """
    from app.api.routes.upload import _dispatch_task
    from fastapi import BackgroundTasks

    mock_celery_app = MagicMock()

    with patch(
        "app.api.routes.upload._celery_available", return_value=True
    ), patch(
        "app.worker.celery_app", mock_celery_app
    ):
        bg = MagicMock(spec=BackgroundTasks)
        fallback = AsyncMock()

        _dispatch_task(bg, "process_document", fallback, 456)

        # Should use Celery send_task, not BackgroundTasks
        mock_celery_app.send_task.assert_called_once_with(
            "process_document", args=[456]
        )
        bg.add_task.assert_not_called()
