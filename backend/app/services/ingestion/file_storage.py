"""
services/ingestion/file_storage.py
────────────────────────────────────
Handles all file I/O for the ingestion pipeline.

Responsibilities:
    - Save uploaded PDFs to the correct storage folder
    - Save extracted images to the images folder
    - Generate clean, collision-free filenames
    - Return file paths for DB storage

Phase 1: local filesystem
Phase 2 (later): swap to S3-compatible object storage
"""

import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from loguru import logger

from app.core.config import settings
from app.models.document import DocumentType


# ── Storage Folder Map ────────────────────────────────────────────────────────

STORAGE_ROOTS = {
    DocumentType.PYQ:       Path(settings.PDF_STORAGE_PATH) / "pyqs",
    DocumentType.NCERT:     Path(settings.PDF_STORAGE_PATH) / "ncerts",
    DocumentType.BOOK:      Path(settings.PDF_STORAGE_PATH) / "books",
    DocumentType.NOTES:     Path(settings.PDF_STORAGE_PATH) / "notes",
    DocumentType.SYLLABUS:  Path(settings.PDF_STORAGE_PATH) / "syllabus",
    DocumentType.NEWSPAPER: Path(settings.NEWSPAPER_STORAGE_PATH),
    DocumentType.JSON:      Path(settings.PDF_STORAGE_PATH) / "notes",
    DocumentType.OTHER:     Path(settings.PDF_STORAGE_PATH) / "notes",
}

IMAGE_ROOT = Path(settings.IMAGE_STORAGE_PATH)
TEMP_ROOT  = Path(settings.TEMP_PATH)


# ── Helpers ───────────────────────────────────────────────────────────────────

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(original_name: str) -> str:
    """
    Generates a unique, filesystem-safe filename.
    Format: YYYYMMDD_HHMMSS_<uuid4_short>_<original_stem>.ext
    """
    stem = Path(original_name).stem
    ext  = Path(original_name).suffix or ".pdf"

    # Strip unsafe chars from original name
    safe_stem = "".join(c if c.isalnum() or c in "-_ " else "_" for c in stem)
    safe_stem = safe_stem[:40].strip("_")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid       = str(uuid.uuid4())[:8]

    return f"{timestamp}_{uid}_{safe_stem}{ext}"


# ── PDF Storage ───────────────────────────────────────────────────────────────

def save_uploaded_pdf(
    file_bytes: bytes,
    original_filename: str,
    doc_type: DocumentType,
) -> str:
    """
    Saves an uploaded PDF to the correct storage folder.

    Returns:
        Absolute path string of the saved file.
    """
    folder = ensure_dir(STORAGE_ROOTS.get(doc_type, STORAGE_ROOTS[DocumentType.OTHER]))
    filename = safe_filename(original_filename)
    dest_path = folder / filename

    with open(dest_path, "wb") as f:
        f.write(file_bytes)

    logger.info(f"💾 Saved PDF: {dest_path} ({len(file_bytes) // 1024} KB)")
    return str(dest_path)


def save_pdf_from_path(src_path: str, doc_type: DocumentType) -> str:
    """
    Copies a PDF that's already on disk to the correct storage folder.
    Used when processing files from temp storage.
    """
    folder    = ensure_dir(STORAGE_ROOTS.get(doc_type, STORAGE_ROOTS[DocumentType.OTHER]))
    filename  = safe_filename(Path(src_path).name)
    dest_path = folder / filename
    shutil.copy2(src_path, dest_path)
    return str(dest_path)


# ── Image Storage ─────────────────────────────────────────────────────────────

def save_image(
    image_bytes: bytes,
    document_id: int,
    page_number: int,
    image_index: int,
) -> str:
    """
    Saves an extracted image to the images folder.

    Organizes by document_id so images stay grouped:
        storage/images/<document_id>/page<N>_img<M>.png

    Returns:
        Absolute path string of the saved image.
    """
    folder = ensure_dir(IMAGE_ROOT / str(document_id))
    filename  = f"page{page_number:04d}_img{image_index:03d}.png"
    dest_path = folder / filename

    with open(dest_path, "wb") as f:
        f.write(image_bytes)

    return str(dest_path)


# ── Temp File Handling ────────────────────────────────────────────────────────

def save_to_temp(file_bytes: bytes, suffix: str = ".pdf") -> str:
    """
    Saves bytes to a temp file for processing.
    Caller is responsible for deleting after use.
    """
    ensure_dir(TEMP_ROOT)
    filename  = f"temp_{uuid.uuid4().hex}{suffix}"
    temp_path = TEMP_ROOT / filename

    with open(temp_path, "wb") as f:
        f.write(file_bytes)

    return str(temp_path)


def delete_temp_file(path: str):
    """Safely deletes a temp file."""
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except Exception as e:
        logger.warning(f"Could not delete temp file {path}: {e}")


# ── File Info ─────────────────────────────────────────────────────────────────

def get_file_size_kb(path: str) -> float:
    """Returns file size in KB."""
    try:
        return round(os.path.getsize(path) / 1024, 2)
    except Exception:
        return 0.0
