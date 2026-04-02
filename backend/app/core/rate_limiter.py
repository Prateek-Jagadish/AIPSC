"""
core/rate_limiter.py
────────────────────
API rate limiting to protect OpenAI-backed endpoints from abuse.

Uses slowapi (built on limits library) with per-IP throttling.
Heavier limits on endpoints that trigger GPT-4o calls (query, answer, revision).
Lighter limits on read-only endpoints (status, documents, health).

Usage in routes:
    from app.core.rate_limiter import limiter

    @router.post("/")
    @limiter.limit("10/minute")
    async def my_endpoint(request: Request, ...):
        ...
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI

from app.core.config import settings


# ── Limiter Instance ──────────────────────────────────────────────────────────

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],           # default: 60 req/min per IP
    storage_uri=settings.REDIS_URL,         # use Redis if available
    strategy="fixed-window",
    enabled=not settings.DEBUG,             # disabled in dev for convenience
)


# ── Rate Limit Tiers ──────────────────────────────────────────────────────────
# Import these in route files for consistent limits across the app.

# Heavy endpoints (GPT-4o calls: ~$0.01-0.05 per request)
RATE_LLM_HEAVY   = "10/minute"     # query, answer writing, probable questions
RATE_LLM_MEDIUM  = "20/minute"     # revision, analytics with LLM summary

# Upload endpoints (trigger background processing)
RATE_UPLOAD       = "5/minute"      # PDF/newspaper/JSON uploads

# Read-only endpoints (DB queries only, no LLM)
RATE_READ         = "60/minute"     # status checks, document listing, history

# Health check (should never be throttled in practice)
RATE_HEALTH       = "120/minute"


# ── Attach to App ─────────────────────────────────────────────────────────────

def setup_rate_limiter(app: FastAPI) -> None:
    """
    Call this in main.py to attach the rate limiter to the FastAPI app.
    Also registers the custom 429 error handler.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
