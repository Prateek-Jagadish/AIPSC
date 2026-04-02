"""
core/config.py
──────────────
Central configuration for the UPSC Intelligence System.
All settings are loaded from .env using pydantic-settings.
Access anywhere via:  from app.core.config import settings
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────
    APP_NAME: str = "UPSC Intelligence System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"

    # ── Database ─────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://upsc_user:password@localhost:5432/upsc_db"
    )
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "upsc_db"
    POSTGRES_USER: str = "upsc_user"
    POSTGRES_PASSWORD: str = "password"

    # ── OpenAI ───────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    OPENAI_CHAT_MODEL: str = "gpt-4o"

    # ── Storage ──────────────────────────────
    STORAGE_BASE_PATH: str = "../storage"
    PDF_STORAGE_PATH: str = "../storage/pdfs"
    IMAGE_STORAGE_PATH: str = "../storage/images"
    NEWSPAPER_STORAGE_PATH: str = "../storage/newspapers"
    TEMP_PATH: str = "../storage/temp"

    # AWS (Phase 2)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_REGION: str = "ap-south-1"

    # ── Redis / Celery ────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── OCR ──────────────────────────────────
    TESSERACT_CMD: str = "/usr/bin/tesseract"

    # ── Chunking ─────────────────────────────
    CHUNK_SIZE: int = 800       # tokens per chunk
    CHUNK_OVERLAP: int = 100    # overlap between consecutive chunks

    # ── Retrieval ────────────────────────────
    VECTOR_SEARCH_LIMIT: int = 10
    KEYWORD_SEARCH_LIMIT: int = 10
    FINAL_CONTEXT_LIMIT: int = 5

    # ── Exam Weights ─────────────────────────
    MAINS_WEIGHT: float = 0.60
    PRELIMS_WEIGHT: float = 0.40

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    Use this instead of importing Settings directly
    so the .env file is only read once.
    """
    return Settings()


# Global singleton — import this everywhere
settings = get_settings()
