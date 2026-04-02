"""
main.py
───────
FastAPI application entry point for the UPSC Intelligence System.

Start the server:
    uvicorn app.main:app --reload --port 8000

Swagger docs available at:
    http://localhost:8000/docs
"""

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from contextlib import asynccontextmanager
from loguru import logger
import sys

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.rate_limiter import setup_rate_limiter
from app.core.error_handlers import setup_error_handlers

# ── Route imports (will be added as we build each module) ─────────────────────
from app.api.routes import upload, query, analytics, revision, health, visuals


# ── Logging Setup ─────────────────────────────────────────────────────────────

logger.remove()  # remove default handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True,
)
logger.add(
    "logs/upsc_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
)


# ── App Lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs startup logic before the first request,
    and cleanup logic after the last request.
    """
    logger.info("🚀 Starting UPSC Intelligence System...")
    await init_db()

    # Pre-load taxonomy into memory so tagging is fast from first request
    try:
        from app.core.database import AsyncSessionFactory
        from app.services.tagging.taxonomy_cache import load_taxonomy
        async with AsyncSessionFactory() as db:
            await load_taxonomy(db)
    except Exception as e:
        logger.warning(f"⚠️  Taxonomy pre-load skipped (run seed_taxonomy.py first): {e}")

    logger.info(f"✅ App ready | env={settings.APP_ENV} | debug={settings.DEBUG}")
    yield
    logger.info("🛑 Shutting down...")
    await close_db()


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "A multimodal, memory-aware UPSC intelligence system. "
        "Handles PDFs, scanned docs, newspapers, maps/images, PYQs, "
        "and conversation-based weakness detection."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rate Limiting ─────────────────────────────────────────────────────────────

setup_rate_limiter(app)


# ── Error Handlers ────────────────────────────────────────────────────────────

setup_error_handlers(app)


# ── Routers ───────────────────────────────────────────────────────────────────

api_router = APIRouter()
api_router.include_router(health.router,    prefix="/health",    tags=["Health"])
api_router.include_router(upload.router,    prefix="/upload",    tags=["Upload"])
api_router.include_router(query.router,     prefix="/query",     tags=["Query"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(revision.router,  prefix="/revision",  tags=["Revision"])
api_router.include_router(visuals.router,   prefix="/visuals",   tags=["Visuals"])

app.include_router(api_router, prefix="/api")


# ── Static File / React App Serving ───────────────────────────────────────────

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend/dist"))

if os.path.exists(frontend_dist):
    logger.info(f"Serve React SPA from: {frontend_dist}")
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Serve exact file if exists
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # Catch-all: React Router index.html
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    @app.get("/", tags=["Root"])
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "message": "React frontend dist folder not found. API is live under /api."
        }
