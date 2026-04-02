"""
services/ingestion/pdf_detector.py
───────────────────────────────────
Detects the nature of a PDF before processing:
    - TEXT_BASED  → has selectable text, extract directly
    - SCANNED     → image-only pages, needs OCR
    - MIXED       → some pages have text, some are scanned

This runs FIRST in the pipeline to route the PDF correctly.
"""

import fitz  # PyMuPDF
from pathlib import Path
from loguru import logger
from dataclasses import dataclass

from app.models.document import PDFType


# ── Constants ─────────────────────────────────────────────────────────────────

# Minimum characters per page to consider it "text-based"
MIN_TEXT_CHARS_PER_PAGE = 50

# If >= this % of pages have text → TEXT_BASED
TEXT_PAGE_THRESHOLD = 0.85

# If <= this % of pages have text → SCANNED
SCANNED_PAGE_THRESHOLD = 0.15


# ── Result Dataclass ──────────────────────────────────────────────────────────

@dataclass
class PDFDetectionResult:
    pdf_type: PDFType
    page_count: int
    text_page_count: int
    scanned_page_count: int
    text_page_ratio: float          # 0.0 – 1.0
    has_images: bool
    estimated_image_count: int
    notes: str = ""


# ── Detector ──────────────────────────────────────────────────────────────────

class PDFDetector:
    """
    Opens a PDF and inspects each page to determine its type.

    Usage:
        detector = PDFDetector()
        result = detector.detect("path/to/file.pdf")
        print(result.pdf_type)   # PDFType.SCANNED
    """

    def detect(self, file_path: str | Path) -> PDFDetectionResult:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        logger.info(f"🔍 Detecting PDF type: {file_path.name}")

        doc = fitz.open(str(file_path))
        page_count = len(doc)

        text_pages = 0
        scanned_pages = 0
        total_images = 0

        for page_num in range(page_count):
            page = doc[page_num]

            # Count images on this page
            image_list = page.get_images(full=False)
            total_images += len(image_list)

            # Extract text from the page
            text = page.get_text("text").strip()

            if len(text) >= MIN_TEXT_CHARS_PER_PAGE:
                text_pages += 1
            else:
                scanned_pages += 1

        doc.close()

        text_ratio = text_pages / page_count if page_count > 0 else 0.0

        # Classify
        if text_ratio >= TEXT_PAGE_THRESHOLD:
            pdf_type = PDFType.TEXT_BASED
            notes = f"{text_pages}/{page_count} pages have selectable text."
        elif text_ratio <= SCANNED_PAGE_THRESHOLD:
            pdf_type = PDFType.SCANNED
            notes = f"Mostly image-based. {scanned_pages}/{page_count} pages need OCR."
        else:
            pdf_type = PDFType.MIXED
            notes = (
                f"Mixed: {text_pages} text pages, "
                f"{scanned_pages} scanned pages out of {page_count}."
            )

        result = PDFDetectionResult(
            pdf_type=pdf_type,
            page_count=page_count,
            text_page_count=text_pages,
            scanned_page_count=scanned_pages,
            text_page_ratio=text_ratio,
            has_images=total_images > 0,
            estimated_image_count=total_images,
            notes=notes,
        )

        logger.info(
            f"  → Type: {pdf_type} | Pages: {page_count} | "
            f"Text: {text_pages} | Scanned: {scanned_pages} | "
            f"Images: {total_images}"
        )

        return result
