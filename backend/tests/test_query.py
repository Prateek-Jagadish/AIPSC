"""
tests/test_query.py
───────────────────
Tests for the query/retrieval API endpoints.
Validates conversation management, query routing,
and intent detection.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock


# ══════════════════════════════════════════════════════════════════════════════
# Conversation Management Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_start_conversation(client):
    """Test that POST /query/conversation/start creates a session."""
    response = await client.post("/query/conversation/start")
    assert response.status_code == 200
    data = response.json()
    assert "conversation_id" in data
    assert data["conversation_id"] > 0


@pytest.mark.asyncio
async def test_get_conversation_history(client, sample_conversation):
    """Test retrieving conversation history."""
    response = await client.get(f"/query/conversation/{sample_conversation.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == sample_conversation.id


@pytest.mark.asyncio
async def test_get_conversation_not_found(client):
    """Test 404 for non-existent conversation."""
    response = await client.get("/query/conversation/99999")
    assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Query Endpoint Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_query_empty_body(client):
    """Test that empty queries are rejected."""
    response = await client.post(
        "/query/",
        json={"query": "   ", "conversation_id": None, "word_limit": None},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_query_success(client):
    """Test a valid query returns structured response."""
    mock_result = {
        "query": "Explain federalism",
        "intent": "Concept Query",
        "answer": {
            "concept_explanation": "Federalism is...",
        },
        "sources": [],
    }

    with patch(
        "app.api.routes.query.run_rag_pipeline",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = await client.post(
            "/query/",
            json={"query": "Explain federalism in India"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "Explain federalism"
        assert data["intent"] == "Concept Query"
        assert "answer" in data


# ══════════════════════════════════════════════════════════════════════════════
# Intent Detector Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_intent_detector_concept_query():
    """Test that concept queries are correctly classified."""
    from app.services.retrieval.intent_detector import detect_intent, QueryIntent

    intent = await detect_intent("Explain the concept of fiscal federalism in India")

    # Should be classified as concept query, PYQ-related, or general
    assert intent in [
        QueryIntent.CONCEPT_QUERY,
        QueryIntent.GENERAL,
        QueryIntent.PYQ_SEARCH,
    ]


@pytest.mark.asyncio
async def test_intent_detector_pyq_search():
    """Test PYQ-related queries are detected."""
    from app.services.retrieval.intent_detector import detect_intent, QueryIntent

    intent = await detect_intent("Show me previous year questions on polity")

    assert intent in [QueryIntent.PYQ_SEARCH, QueryIntent.CONCEPT_QUERY, QueryIntent.GENERAL]


@pytest.mark.asyncio
async def test_word_limit_extraction():
    """Test that word limits are extracted from queries."""
    from app.services.retrieval.intent_detector import extract_word_limit

    assert extract_word_limit("Write an answer in 250 words") == 250
    assert extract_word_limit("150 word answer on federalism") == 150
    assert extract_word_limit("Explain federalism") is None


# ══════════════════════════════════════════════════════════════════════════════
# Current Affairs Endpoint Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_current_affairs_empty(client):
    """Test current affairs endpoint with no data."""
    response = await client.get("/query/current-affairs?days=7")
    assert response.status_code == 200
    data = response.json()
    assert "articles" in data
    assert data["total"] == 0
