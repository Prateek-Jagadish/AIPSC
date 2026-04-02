"""
utils/file_utils.py
───────────────────
Shared file handling utilities used across all ingestion services.
Handles path generation, file type detection, and safe storage.
"""

import os
import uuid
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from loguru import logger
from app.core.config import settings
from app.models.document import DocumentType, PDFType


# ── Path Helpers ──────────────────────────────────────────────────────────────

def get_storage_path(doc_type: DocumentType) -> Path:
    """Return the correct storage folder for a document type."""
    mapping = {
        DocumentType.PYQ:       Path(settings.PDF_STORAGE_PATH) / "pyqs",
        DocumentType.NCERT:     Path(settings.PDF_STORAGE_PATH) / "ncerts",
        DocumentType.BOOK:      Path(settings.PDF_STORAGE_PATH) / "books",
        DocumentType.NOTES:     Path(settings.PDF_STORAGE_PATH) / "notes",
        DocumentType.SYLLABUS:  Path(settings.PDF_STORAGE_PATH) / "syllabus",
        DocumentType.NEWSPAPER: Path(settings.NEWSPAPER_STORAGE_PATH),
        DocumentType.JSON:      Path(settings.PDF_STORAGE_PATH) / "notes",
        DocumentType.OTHER:     Path(settings.PDF_STORAGE_PATH) / "notes",
    }
    folder = mapping.get(doc_type, Path(settings.PDF_STORAGE_PATH))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def generate_unique_filename(original_name: str) -> str:
    """Generate a unique filename to avoid collisions."""
    ext = Path(original_name).suffix.lower()
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = Path(original_name).stem[:40].replace(" ", "_")
    return f"{timestamp}_{safe_name}_{unique_id}{ext}"


def get_image_storage_path(document_id: int) -> Path:
    """Return storage folder for images extracted from a specific document."""
    folder = Path(settings.IMAGE_STORAGE_PATH) / f"doc_{document_id}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_temp_path() -> Path:
    """Return temp folder for intermediate OCR files."""
    folder = Path(settings.TEMP_PATH)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def cleanup_temp_file(path: str) -> None:
    """Delete a temp file safely."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning(f"Could not delete temp file {path}: {e}")


# ── File Info ─────────────────────────────────────────────────────────────────

def get_file_size_kb(file_path: str) -> float:
    """Return file size in KB."""
    try:
        return os.path.getsize(file_path) / 1024
    except Exception:
        return 0.0


def compute_file_hash(file_path: str) -> str:
    """Compute MD5 hash of a file for deduplication."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
    except Exception as e:
        logger.warning(f"Could not hash file {file_path}: {e}")
    return hash_md5.hexdigest()


# ── PDF Type Detection ────────────────────────────────────────────────────────

def detect_pdf_type(file_path: str) -> PDFType:
    """
    Detect whether a PDF is text-based, scanned, or mixed.
    
    Logic:
        - Open each page with PyMuPDF
        - If a page has extractable text → text-based
        - If a page has no text but has images → scanned
        - Mix of both → mixed
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        text_pages = 0
        scanned_pages = 0

        for page in doc:
            text = page.get_text("text").strip()
            images = page.get_images(full=True)

            if len(text) > 50:       # meaningful text present
                text_pages += 1
            elif len(images) > 0:    # only images, no text
                scanned_pages += 1

        doc.close()

        total = text_pages + scanned_pages
        if total == 0:
            return PDFType.TEXT_BASED   # empty PDF, treat as text

        scanned_ratio = scanned_pages / total

        if scanned_ratio > 0.8:
            return PDFType.SCANNED
        elif scanned_ratio < 0.2:
            return PDFType.TEXT_BASED
        else:
            return PDFType.MIXED

    except Exception as e:
        logger.error(f"Error detecting PDF type for {file_path}: {e}")
        return PDFType.TEXT_BASED   # safe fallback


def is_valid_pdf(file_path: str) -> bool:
    """Check if a file is a valid PDF."""
    try:
        import fitz
        doc = fitz.open(file_path)
        _ = len(doc)
        doc.close()
        return True
    except Exception:
        return False
