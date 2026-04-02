# ─────────────────────────────────────────────────────────────────
# UPSC Intelligence System — Backend Dockerfile
# ─────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# System dependencies (Tesseract OCR + Ghostscript for OCRmyPDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    ghostscript \
    pngquant \
    unpaper \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Create storage directories
RUN mkdir -p storage/pdfs/pyqs storage/pdfs/ncerts storage/pdfs/books \
    storage/pdfs/notes storage/pdfs/syllabus \
    storage/images storage/newspapers storage/temp logs

# Expose port
EXPOSE 8000

# Default: run FastAPI (overridden by docker-compose for worker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
