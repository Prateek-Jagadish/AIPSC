"""
tests/test_upload.py
────────────────────
Tests for the upload API endpoints.
Validates PDF upload flow, newspaper routing, and status endpoints.

Uses mocked file storage and ingestion services to avoid actual
PDF processing during tests.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from io import BytesIO


# ══════════════════════════════════════════════════════════════════════════════
# Upload Validation Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_upload_pdf_success(client):
    """Test that a valid PDF upload returns 200 with document_id."""
    # Create a minimal valid PDF bytes
    pdf_bytes = b"%PDF-1.4 test content"

    with patch(
        "app.api.routes.upload.register_document",
        new_callable=AsyncMock,
    ) as mock_register, patch(
        "app.api.routes.upload._dispatch_task"
    ) as mock_dispatch:
        # Mock the register to return a fake document
        mock_doc = MagicMock()
        mock_doc.id = 1
        mock_doc.title = "Test PDF"
        mock_doc.status = MagicMock(value="Uploaded")
        mock_register.return_value = mock_doc

        response = await client.post(
            "/upload/pdf",
            files={"file": ("test.pdf", BytesIO(pdf_bytes), "application/pdf")},
            data={"doc_type": "Notes", "title": "Test PDF"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == 1
        assert data["status"] == "Uploaded"
        assert "Track at" in data["message"]


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client):
    """Test that non-PDF files are rejected."""
    response = await client.post(
        "/upload/pdf",
        files={"file": ("test.txt", BytesIO(b"not a pdf"), "text/plain")},
        data={"doc_type": "Notes"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_newspaper_uses_correct_pipeline(client):
    """
    Bug 1 regression test: newspaper uploads must route through
    _bg_process_newspaper (which calls process_newspaper),
    NOT through _bg_process (which calls process_document).
    """
    pdf_bytes = b"%PDF-1.4 newspaper content"

    with patch(
        "app.api.routes.upload.register_document",
        new_callable=AsyncMock,
    ) as mock_register, patch(
        "app.api.routes.upload._dispatch_task"
    ) as mock_dispatch:
        mock_doc = MagicMock()
        mock_doc.id = 2
        mock_doc.title = "The Hindu — 02 Apr 2026"
        mock_doc.status = MagicMock(value="Uploaded")
        mock_register.return_value = mock_doc

        response = await client.post(
            "/upload/newspaper",
            files={"file": ("hindu.pdf", BytesIO(pdf_bytes), "application/pdf")},
            data={"publication": "The Hindu", "publish_date": "2026-04-02"},
        )

        assert response.status_code == 200

        # Verify the dispatch was called with "process_newspaper" task name
        mock_dispatch.assert_called_once()
        call_args = mock_dispatch.call_args
        assert call_args[0][1] == "process_newspaper"  # celery_task_name

        data = response.json()
        assert "UPSC filtering" in data["message"]


@pytest.mark.asyncio
async def test_upload_newspaper_invalid_date(client):
    """Test that invalid publish_date is rejected."""
    pdf_bytes = b"%PDF-1.4 newspaper content"

    response = await client.post(
        "/upload/newspaper",
        files={"file": ("hindu.pdf", BytesIO(pdf_bytes), "application/pdf")},
        data={"publication": "The Hindu", "publish_date": "not-a-date"},
    )
    assert response.status_code == 400
    assert "date format" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_json_validates_json(client):
    """Test that invalid JSON files are rejected."""
    response = await client.post(
        "/upload/json",
        files={"file": ("pyqs.json", BytesIO(b"not valid json"), "application/json")},
    )
    assert response.status_code == 400
    assert "Invalid JSON" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_json_rejects_non_json(client):
    """Test that non-.json files are rejected."""
    response = await client.post(
        "/upload/json",
        files={"file": ("test.txt", BytesIO(b"{}"), "text/plain")},
    )
    assert response.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# Status Endpoint Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_document_status(client, sample_document):
    """Test fetching document processing status."""
    response = await client.get(f"/upload/status/{sample_document.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == sample_document.id
    assert data["title"] == sample_document.title


@pytest.mark.asyncio
async def test_get_document_status_not_found(client):
    """Test 404 for non-existent document."""
    response = await client.get("/upload/status/99999")
    assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Document Listing Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_documents_empty(client):
    """Test listing documents when none exist."""
    response = await client.get("/upload/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["documents"] == []


@pytest.mark.asyncio
async def test_list_documents_with_data(client, sample_document):
    """Test listing documents when data exists."""
    response = await client.get("/upload/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(d["id"] == sample_document.id for d in data["documents"])
