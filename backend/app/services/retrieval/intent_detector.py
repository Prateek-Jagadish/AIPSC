"""
services/retrieval/intent_detector.py
───────────────────────────────────────
Classifies user queries into intent categories.
This determines which handler the RAG pipeline routes to.

Uses a fast keyword-based classifier first (no LLM call).
Falls back to LLM classification for ambiguous queries.

Intents:
    CONCEPT_QUERY      → explain / what is / tell me about
    PYQ_SEARCH         → PYQ / previous year / past questions
    TREND_ANALYSIS     → trend / pattern / recurring / frequency
    ANSWER_WRITING     → write answer / 250 words / mains answer
    PROBABLE_QUESTIONS → probable / likely / predict / 5 questions
    MAP_QUERY          → map / diagram / location / visual / table
    WEAKNESS_CHECK     → weak / lag / concentrate / gap / missing
    REVISION           → revise / cheat sheet / summary / week
    CA_LINK            → news / current affairs / today / recent
    GENERAL            → everything else
"""

import enum
import re
from loguru import logger


class QueryIntent(str, enum.Enum):
    CONCEPT_QUERY      = "Concept Query"
    PYQ_SEARCH         = "PYQ Search"
    TREND_ANALYSIS     = "Trend Analysis"
    ANSWER_WRITING     = "Answer Writing"
    PROBABLE_QUESTIONS = "Probable Questions"
    MAP_QUERY          = "Map Query"
    WEAKNESS_CHECK     = "Weakness Check"
    REVISION           = "Revision"
    CA_LINK            = "CA Link"
    GENERAL            = "General"


# ── Keyword Rules ─────────────────────────────────────────────────────────────

_INTENT_RULES: list[tuple[QueryIntent, list[str]]] = [
    (QueryIntent.WEAKNESS_CHECK, [
        "where am i weak", "lagging", "concentrate", "gaps", "missing topics",
        "not covering", "weakest", "neglecting", "anomaly", "i should focus",
    ]),
    (QueryIntent.REVISION, [
        "revision", "cheat sheet", "cheatsheet", "revise", "weekly summary",
        "monthly summary", "this week", "this month", "quick review",
    ]),
    (QueryIntent.ANSWER_WRITING, [
        "write answer", "write a", "250 word", "150 word", "mains answer",
        "model answer", "answer structure", "write on", "answer for",
        "approach the answer", "guide me how",
    ]),
    (QueryIntent.PROBABLE_QUESTIONS, [
        "probable", "likely question", "predict", "5 questions", "possible question",
        "may appear", "might ask", "expected question", "guess questions",
    ]),
    (QueryIntent.PYQ_SEARCH, [
        "pyq", "previous year", "past question", "past year", "2016", "2017",
        "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025",
        "asked before", "appeared in exam",
    ]),
    (QueryIntent.TREND_ANALYSIS, [
        "trend", "pattern", "recurring", "frequency", "how many times",
        "which year", "year-wise", "repeated", "often asked", "theme",
    ]),
    (QueryIntent.MAP_QUERY, [
        "map", "location", "diagram", "table", "graph", "chart",
        "visual", "image", "where is", "place", "region", "show me",
        "geographic", "mapping question",
    ]),
    (QueryIntent.CA_LINK, [
        "current affairs", "today", "recent", "news", "this year",
        "latest", "newspaper", "what's happening", "developments",
    ]),
    (QueryIntent.CONCEPT_QUERY, [
        "explain", "what is", "what are", "tell me", "describe",
        "define", "concept", "meaning", "overview", "introduction to",
        "understand", "learn about", "how does", "why is",
    ]),
]


# ── Detector ──────────────────────────────────────────────────────────────────

async def detect_intent(query: str) -> QueryIntent:
    """
    Classifies a user query into a QueryIntent.

    Strategy:
        1. Normalize query to lowercase
        2. Scan keyword rules in priority order
        3. Return first match
        4. Fall back to GENERAL if no match

    No LLM call — pure keyword matching for speed.
    The routing logic in rag_pipeline.py handles ambiguous cases gracefully.
    """
    query_lower = query.lower().strip()

    for intent, keywords in _INTENT_RULES:
        for kw in keywords:
            if kw in query_lower:
                logger.debug(f"  Intent matched: {intent} (keyword: '{kw}')")
                return intent

    # Special case: if query ends with "?" and is short → concept query
    if query.strip().endswith("?") and len(query.split()) < 15:
        return QueryIntent.CONCEPT_QUERY

    return QueryIntent.GENERAL


def extract_word_limit(query: str) -> int:
    """
    Extracts requested word limit from answer-writing queries.
    Defaults to 250 if not specified.
    """
    patterns = [
        r'(\d+)\s*word',
        r'(\d+)\s*-?\s*words',
        r'in\s*(\d+)\s*words',
    ]
    for pattern in patterns:
        match = re.search(pattern, query.lower())
        if match:
            limit = int(match.group(1))
            if 50 <= limit <= 1000:
                return limit
    return 250   # default mains word limit
