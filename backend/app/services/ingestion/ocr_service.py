"""
services/ingestion/ocr_service.py
──────────────────────────────────
Handles OCR for scanned PDFs.

Flow:
    1. Detect if PDF needs OCR (already done in file_utils)
    2. Run OCRmyPDF to add a searchable text layer
    3. Return path to the OCR-processed PDF (new file, original kept)

We never overwrite the original — OCR output is a separate file
stored in the temp directory, then moved to the document's folder.

Tools:
    - OCRmyPDF: adds invisible text layer to scanned PDFs
    - Tesseract: underlying OCR engine used by OCRmyPDF
"""

import os
import shutil
from pathlib import Path

from loguru import logger

from app.core.config import settings
from app.utils.file_utils import get_temp_path, cleanup_temp_file


class OCRService:
    """
    Wraps OCRmyPDF to process scanned PDFs into searchable ones.
    
    Usage:
        service = OCRService()
        ocr_path = await service.process(original_pdf_path)
        # ocr_path is a new PDF with searchable text layer
    """

    def __init__(self):
        self.tesseract_cmd = settings.TESSERACT_CMD
        self._verify_tesseract()

    def _verify_tesseract(self):
        """Check Tesseract is installed and accessible."""
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"✅ Tesseract version: {version}")
        except Exception as e:
            logger.warning(f"⚠️  Tesseract not found at {self.tesseract_cmd}: {e}")
            logger.warning("OCR will not work. Install tesseract-ocr.")

    def process(self, input_pdf_path: str) -> str:
        """
        Run OCR on a scanned PDF and return path to the output PDF.
        
        The output PDF is identical to the input but now has a
        searchable text layer — images are preserved exactly.
        
        Args:
            input_pdf_path: Path to the scanned PDF file
            
        Returns:
            Path to OCR-processed PDF (new file in temp directory)
            
        Raises:
            RuntimeError: If OCR fails
        """
        import ocrmypdf

        input_path = Path(input_pdf_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input PDF not found: {input_pdf_path}")

        # Output in temp directory with "_ocr" suffix
        temp_dir = get_temp_path()
        output_filename = input_path.stem + "_ocr" + input_path.suffix
        output_path = temp_dir / output_filename

        logger.info(f"🔍 Starting OCR: {input_path.name}")

        try:
            ocrmypdf.ocr(
                input_file=str(input_path),
                output_file=str(output_path),
                language="eng",                 # English only
                deskew=True,                    # correct skewed scans
                clean=True,                     # remove scanning artifacts
                optimize=1,                     # light optimization (fast)
                skip_text=True,                 # skip pages that already have text
                progress_bar=False,
                jobs=2,                         # parallel processing
            )
            logger.success(f"✅ OCR complete: {output_path.name}")
            return str(output_path)

        except ocrmypdf.exceptions.PriorOcrFoundError:
            # PDF already has text — use original
            logger.info("ℹ️  PDF already has text layer — skipping OCR")
            return str(input_path)

        except ocrmypdf.exceptions.EncryptedPdfError:
            raise RuntimeError(f"PDF is encrypted and cannot be OCR'd: {input_path.name}")

        except Exception as e:
            logger.error(f"❌ OCR failed for {input_path.name}: {e}")
            raise RuntimeError(f"OCR processing failed: {str(e)}")

    def process_mixed(self, input_pdf_path: str) -> str:
        """
        Process a mixed PDF (some pages text, some scanned).
        OCRmyPDF's skip_text=True handles this automatically.
        Same as process() but explicitly for mixed PDFs.
        """
        logger.info(f"🔍 Processing mixed PDF: {Path(input_pdf_path).name}")
        return self.process(input_pdf_path)

    @staticmethod
    def extract_text_from_image(image_path: str) -> str:
        """
        Extract text from a single image (used for image OCR in PDFs).
        
        Args:
            image_path: Path to image file (PNG, JPG, etc.)
            
        Returns:
            Extracted text string (empty string if none found)
        """
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(image_path)
            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 3"  # fully automatic page segmentation
            )
            return text.strip()

        except Exception as e:
            logger.warning(f"Image OCR failed for {image_path}: {e}")
            return ""
