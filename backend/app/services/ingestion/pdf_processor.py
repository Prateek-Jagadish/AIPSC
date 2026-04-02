"""
services/ingestion/pdf_processor.py
─────────────────────────────────────
Core PDF processing engine.

Responsibilities:
    1. Detect whether a PDF is text-based, scanned, or mixed
    2. Run OCR on scanned pages (OCRmyPDF + Tesseract)
    3. Extract clean text per page
    4. Extract all images (maps, tables, diagrams, photos) per page
    5. Return structured PageData objects

Used by: document_ingestion_service.py (the orchestrator)
"""

import fitz          # PyMuPDF
import ocrmypdf
import pytesseract
from PIL import Image
from dataclasses import dataclass, field
from typing import Optional
import tempfile
import shutil
import io
import os

from loguru import logger


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class ExtractedImage:
    """One image extracted from a PDF page."""
    page_number:      int
    image_index:      int
    image_bytes:      bytes
    width:            int
    height:           int
    ocr_text:         str = ""
    surrounding_text: str = ""


@dataclass
class PageData:
    """All content extracted from one PDF page."""
    page_number: int
    text:        str
    images:      list = field(default_factory=list)
    was_ocr:     bool = False
    word_count:  int = 0


@dataclass
class PDFExtractionResult:
    """Full extraction result for one PDF file."""
    file_path:   str
    pdf_type:    str           # "Text", "Scanned", "Mixed"
    total_pages: int
    pages:       list = field(default_factory=list)
    ocr_applied: bool = False
    error:       Optional[str] = None


# ── PDF Type Detection ────────────────────────────────────────────────────────

def detect_pdf_type(pdf_path: str) -> str:
    """
    Detects if PDF is Text / Scanned / Mixed.
    Pages with fewer than 50 chars of text are treated as scanned.
    """
    MIN_CHARS = 50
    doc = fitz.open(pdf_path)
    text_pages = scanned_pages = 0

    for page in doc:
        text = page.get_text("text").strip()
        if len(text) >= MIN_CHARS:
            text_pages += 1
        else:
            scanned_pages += 1
    doc.close()

    if scanned_pages == 0:
        return "Text"
    elif text_pages == 0:
        return "Scanned"
    else:
        return "Mixed"


# ── OCR Pipeline ──────────────────────────────────────────────────────────────

def run_ocr_on_pdf(input_path: str, output_path: str) -> bool:
    """
    Adds a searchable text layer to scanned/mixed PDFs using OCRmyPDF.
    Returns True on success, False on failure.
    """
    try:
        ocrmypdf.ocr(
            input_file=input_path,
            output_file=output_path,
            language="eng",
            deskew=True,
            clean=True,
            optimize=1,
            skip_text=True,      # skip pages that already have text (for Mixed)
            progress_bar=False,
            jobs=2,
        )
        logger.info(f"✅ OCR complete: {input_path}")
        return True

    except ocrmypdf.exceptions.PriorOcrFoundError:
        shutil.copy(input_path, output_path)
        return True

    except Exception as e:
        logger.error(f"❌ OCR failed: {e}")
        return False


# ── Image Text Extraction ─────────────────────────────────────────────────────

def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Runs Tesseract OCR on an image to extract any embedded text labels.
    Used for map labels, table headers, diagram annotations.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang="eng", config="--psm 6")
        return text.strip()
    except Exception as e:
        logger.warning(f"Image OCR warning: {e}")
        return ""


# ── Image Extraction per Page ─────────────────────────────────────────────────

def extract_images_from_page(
    page: fitz.Page,
    doc: fitz.Document,
    page_number: int,
    page_text: str,
    min_size_px: int = 100,
) -> list:
    """
    Extracts all meaningful images from a single PDF page.
    Skips tiny images (icons, bullets) below min_size_px.
    Each image gets its embedded text extracted via OCR.
    """
    extracted = []
    image_list = page.get_images(full=True)

    for img_index, img_info in enumerate(image_list):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            pil_image = Image.open(io.BytesIO(image_bytes))
            width, height = pil_image.size

            # Skip decorative tiny images
            if width < min_size_px or height < min_size_px:
                continue

            # Normalize to PNG
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            png_bytes = buf.getvalue()

            ocr_text = extract_text_from_image(png_bytes)
            surrounding = page_text[:500] if page_text else ""

            extracted.append(ExtractedImage(
                page_number=page_number,
                image_index=img_index,
                image_bytes=png_bytes,
                width=width,
                height=height,
                ocr_text=ocr_text,
                surrounding_text=surrounding,
            ))

        except Exception as e:
            logger.warning(f"Image extract warning page {page_number} img {img_index}: {e}")
            continue

    return extracted


# ── Main Entry Point ──────────────────────────────────────────────────────────

def extract_pdf(file_path: str) -> PDFExtractionResult:
    """
    Full pipeline for one PDF:
        1. Detect type (Text / Scanned / Mixed)
        2. OCR if needed
        3. Extract text + images page by page
        4. Return PDFExtractionResult

    This is the only function called externally.
    """
    result = PDFExtractionResult(
        file_path=file_path,
        pdf_type="Text",
        total_pages=0,
    )
    ocr_output = None

    try:
        # Step 1: Detect
        pdf_type = detect_pdf_type(file_path)
        result.pdf_type = pdf_type
        logger.info(f"📄 [{pdf_type}] {file_path}")

        # Step 2: OCR
        working_path = file_path
        if pdf_type in ("Scanned", "Mixed"):
            tmp = tempfile.NamedTemporaryFile(suffix="_ocr.pdf", delete=False)
            ocr_output = tmp.name
            tmp.close()

            success = run_ocr_on_pdf(file_path, ocr_output)
            if success:
                working_path = ocr_output
                result.ocr_applied = True
            else:
                result.error = "OCR failed — continuing without OCR layer"
                logger.warning("⚠️  Continuing without OCR")

        # Step 3: Extract page by page
        doc = fitz.open(working_path)
        result.total_pages = len(doc)

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_number = page_num + 1

            raw_text = page.get_text("text") or ""
            clean_text = raw_text.strip()

            images = extract_images_from_page(
                page=page,
                doc=doc,
                page_number=page_number,
                page_text=clean_text,
            )

            result.pages.append(PageData(
                page_number=page_number,
                text=clean_text,
                images=images,
                was_ocr=result.ocr_applied,
                word_count=len(clean_text.split()) if clean_text else 0,
            ))

        doc.close()

        total_words  = sum(p.word_count for p in result.pages)
        total_images = sum(len(p.images) for p in result.pages)
        logger.info(
            f"✅ Done: {result.total_pages} pages | "
            f"{total_words} words | {total_images} images"
        )

    except Exception as e:
        result.error = str(e)
        logger.error(f"❌ Extraction failed for {file_path}: {e}")

    finally:
        # Cleanup temp OCR file
        if ocr_output and os.path.exists(ocr_output):
            os.unlink(ocr_output)

    return result
