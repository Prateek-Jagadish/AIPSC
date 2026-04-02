#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# UPSC Intelligence System — One-Command Setup Script
# Run this once after cloning the repo:
#   chmod +x setup.sh && ./setup.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e  # exit immediately on any error

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  UPSC Intelligence System — Project Setup"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── Step 1: Python virtual environment ───────────────────────────────────────
echo "📦 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "✅ Virtual environment ready"

# ── Step 2: Install dependencies ─────────────────────────────────────────────
echo ""
echo "📥 Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "✅ Dependencies installed"

# ── Step 3: Environment file ─────────────────────────────────────────────────
echo ""
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ .env created from .env.example"
    echo "⚠️  Please fill in your values in .env before running the server"
else
    echo "✅ .env already exists — skipping"
fi

# ── Step 4: PostgreSQL check ──────────────────────────────────────────────────
echo ""
echo "🗄️  Checking PostgreSQL..."
if command -v psql &> /dev/null; then
    echo "✅ PostgreSQL found"
    echo ""
    echo "Run these commands to create the database:"
    echo "   psql -U postgres"
    echo "   CREATE USER upsc_user WITH PASSWORD 'your-password';"
    echo "   CREATE DATABASE upsc_db OWNER upsc_user;"
    echo "   \\q"
else
    echo "⚠️  PostgreSQL not found — install it:"
    echo "   Ubuntu/Debian: sudo apt install postgresql postgresql-contrib"
    echo "   macOS:         brew install postgresql"
fi

# ── Step 5: pgvector check ────────────────────────────────────────────────────
echo ""
echo "📐 Note: pgvector must be installed in PostgreSQL."
echo "   Ubuntu: sudo apt install postgresql-16-pgvector"
echo "   macOS:  brew install pgvector"
echo "   Or: https://github.com/pgvector/pgvector#installation"

# ── Step 6: Tesseract OCR check ──────────────────────────────────────────────
echo ""
echo "🔍 Checking Tesseract OCR..."
if command -v tesseract &> /dev/null; then
    echo "✅ Tesseract found: $(tesseract --version | head -1)"
else
    echo "⚠️  Tesseract not found — install it:"
    echo "   Ubuntu: sudo apt install tesseract-ocr"
    echo "   macOS:  brew install tesseract"
fi

# ── Step 7: Redis check ───────────────────────────────────────────────────────
echo ""
echo "📮 Checking Redis..."
if command -v redis-cli &> /dev/null; then
    echo "✅ Redis found"
else
    echo "⚠️  Redis not found — install it:"
    echo "   Ubuntu: sudo apt install redis-server"
    echo "   macOS:  brew install redis"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Fill in your .env file"
echo "  2. Set up PostgreSQL + pgvector"
echo "  3. Run:  uvicorn app.main:app --reload --port 8000"
echo "  4. Open: http://localhost:8000/docs"
echo "═══════════════════════════════════════════════════════"
echo ""
