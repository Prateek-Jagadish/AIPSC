# UPSC Intelligence System — Complete Setup Guide

> Your personal AI-powered UPSC study engine.
> From zero to fully running in under 15 minutes.

---

## What You're Getting

A fully integrated UPSC intelligence system with **7 pages**, **20+ API endpoints**, and **5 Docker services**:

| Capability | Description |
|---|---|
| 📄 PDF ingestion (text + scanned) | Upload PYQs, NCERTs, books, notes — OCR runs automatically on scanned PDFs |
| 📰 Daily newspaper → UPSC filter | Upload newspaper PDF → system extracts only UPSC-relevant articles |
| 🏷️ Auto-tagging to topic taxonomy | Every chunk is tagged to Topic → Subtopic → MicroTag using GPT-4o |
| 🔍 RAG-based Q&A | 9 query types: concept, PYQ, trends, answer writing, probable Qs, maps, weakness, revision, CA link |
| 🖼️ Maps/diagrams → AI captioned | Extracted visuals get structured AI descriptions and become searchable |
| ❓ PYQ pattern analysis (2016–2025) | Topic frequency, command word analysis, trend detection |
| 📊 Weakness detection + anomaly alerts | Finds topics you're neglecting that have high PYQ weight |
| 📝 Mains answer writing | Structured answers: intro → body dimensions → conclusion → diagram suggestion |
| 🗓️ Weekly/monthly revision cheat sheets | Combines your gaps, current affairs, PYQ trends, and study history |
| 💬 Conversation memory | Tracks what you've studied, detects gaps over time |
| 🎨 React dashboard | Premium dark-mode UI with 7 pages |

---

## Prerequisites

Before starting, install these on your machine:

| Tool | Version | Install |
|---|---|---|
| **Docker Desktop** | Latest | https://docker.com/products/docker-desktop |
| **Git** | Any | https://git-scm.com |
| **OpenAI Account** | — | https://platform.openai.com |

> **That's it.** Docker handles Python, Node, PostgreSQL, Redis, Tesseract OCR — everything.

---

## Step 1 — Get Your OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Click **Create new secret key**
3. Copy the key (starts with `sk-...`) — you'll need it in Step 3

> The system uses:
> - `gpt-4o` for tagging, captioning, and answer generation
> - `text-embedding-3-large` for semantic search (3072 dimensions)

---

## Step 2 — Download the Project

```bash
git clone <your-repo-url>
cd upsc_intelligence
```

Or extract the zip file. You should see:

```
upsc_intelligence/
├── backend/          # Python FastAPI backend
├── frontend/         # React dashboard
├── storage/          # Uploaded files (auto-created)
├── docker-compose.yml
├── .env.example
├── README.md
└── SETUP_GUIDE.md    # ← You are here
```

---

## Step 3 — Configure Environment

Copy the example environment file and fill in your API key:

```bash
# On Mac/Linux:
cp .env.example .env

# On Windows (PowerShell):
Copy-Item .env.example .env
```

Open `.env` in any text editor and update:

```env
# REQUIRED — your OpenAI API key
OPENAI_API_KEY=sk-your-actual-key-here

# Database password (change this to anything secure)
POSTGRES_PASSWORD=choose_a_strong_password

# Leave the rest as-is for development
APP_ENV=development
DEBUG=true
```

> ⚠️ Never commit `.env` to git. It's already in `.gitignore`.

---

## Step 4 — Start Everything

```bash
docker-compose up --build
```

This will:
1. Pull PostgreSQL 16 (with pgvector) + Redis 7 images
2. Build the Python backend (installs Tesseract OCR, all 30+ Python packages)
3. Build the React frontend (installs Node packages, builds for production)
4. Start all 5 services: **postgres**, **redis**, **backend**, **worker**, **frontend**
5. Run database migrations automatically
6. Seed the UPSC topic taxonomy (15 subjects spanning GS1-GS4/CSAT, 50+ subtopics, 250+ micro-tags)

**First build takes 5–10 minutes** (downloads ~2GB of images).
Subsequent starts take ~20 seconds.

You'll know it's ready when you see:
```
upsc_backend  | ✅ App ready | env=development | debug=True
upsc_backend  | ✅ Taxonomy loaded: 8 topics | 35 subtopics | 180 micro_tags
```

---

## Step 5 — Open the Application

| Service | URL |
|---|---|
| 🖥️ **Frontend Dashboard** | http://localhost:3000 |
| 📖 **API Documentation** | http://localhost:8000/docs |
| ❤️ **Health Check** | http://localhost:8000/health |

---

## Step 6 — Your First Upload

### Option A: Upload the PYQ JSON (do this first)

```
Frontend → Upload → Select type: "Other" → drag your PYQ JSON file
```

This seeds the system with 2016–2025 Mains questions and model answers.
Processing takes ~5 minutes (tagging + embedding all questions).

### Option B: Upload a PYQ Paper PDF

```
Frontend → Upload
→ Select document type: PYQ Paper
→ Enter year (e.g., 2023) and paper (e.g., GS2)
→ Drop the PDF
```

### Option C: Upload Today's Newspaper

```
Frontend → Daily Briefing
→ Select publication (The Hindu, Indian Express, etc.)
→ Set today's date
→ Drop the newspaper PDF
```

UPSC-relevant articles are automatically extracted — usually 10–25 per newspaper.

### Option D: Upload NCERTs / Books / Notes

```
Frontend → Upload
→ Select type (NCERT / Standard Book / Notes)
→ Drop the PDF
```

---

## Step 7 — Start Asking Questions

Go to **Ask & Learn** and try:

| Query | What It Does |
|---|---|
| `Explain Indian Federalism with constitutional provisions and recent issues` | Concept explanation + PYQs + CA linkage |
| `What are recurring themes in GS2 Polity from 2016 to 2025?` | Trend analysis with frequency data |
| `Write a 250-word mains answer on demand and supply` | Structured answer: intro → body → conclusion |
| `Give me 5 probable questions on Indus Valley Civilization` | Probable Qs with probability ratings |
| `Which topics am I lagging in?` | Weakness analysis comparing your coverage vs PYQ weight |
| `Give me my weekly revision cheat sheet` | Prioritized revision plan |
| `Show me maps related to Western Ghats biodiversity` | Visual asset retrieval with AI captions |

---

## Daily Routine

Every morning:

1. **Upload newspaper** → Daily Briefing → drop PDF → wait 2–3 minutes
2. **Check dashboard** → new CA items appear with syllabus mapping
3. **Ask questions** on topics you're studying that day
4. **Weekly** → Revision → Generate Weekly Sheet
5. **Monthly** → Revision → Generate Monthly Sheet

---

## Uploading Your Full Document Library

Upload in this order for best results:

| Order | Documents | Type | Notes |
|---|---|---|---|
| 1 | Syllabus PDFs (6–8 PDFs) | Syllabus | Anchors the taxonomy |
| 2 | PYQ JSON file | JSON Upload | Seeds all 2016–2025 questions |
| 3 | PYQ PDFs (2016–2025, GS1–4 + Essay + Prelims) | PYQ | 70+ PDFs |
| 4 | NCERT PDFs (Class 6–12) | NCERT | Both text and scanned |
| 5 | Standard Books | Standard Book | Laxmikanth, Ramesh Singh, etc. |
| 6 | Your Notes | Notes | Handwritten scans work too |

Each document goes through:
```
Uploaded → Processing (OCR if scanned) → Tagged (GPT-4o) → Embedded (vectors) ✅
```

Status is shown in real time on the Upload page.

---

## Stopping and Restarting

```bash
# Stop all containers (data is preserved)
docker-compose down

# Restart (no rebuild needed)
docker-compose up

# Stop and delete ALL data (fresh start)
docker-compose down -v
docker-compose up --build
```

---

## Viewing Logs

```bash
# All services
docker-compose logs -f

# Just backend
docker-compose logs -f backend

# Just the Celery worker (processing jobs)
docker-compose logs -f worker

# Just database
docker-compose logs -f postgres
```

---

## Local Development (Without Docker)

If you prefer running services directly:

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# Mac/Linux:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, OPENAI_API_KEY, etc.

# Run database migrations
alembic upgrade head

# Seed the UPSC taxonomy
python scripts/seed_taxonomy.py

# Start the server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

### Monolithic Production Native (No-Docker Local)
FastAPI can serve the React static build natively over a singular port to prevent cross-origin issues during native deployment.
1. `cd frontend && npm run build`
2. Restart `uvicorn app.main:app`. The React frontend is now accessible at `http://localhost:8000/`.

### Prerequisites for Local Dev

| Dependency | Install |
|---|---|
| Python 3.11+ | https://python.org |
| Node.js 18+ | https://nodejs.org |
| PostgreSQL 15+ with pgvector | https://github.com/pgvector/pgvector |
| Redis (optional — for Celery) | https://redis.io |
| Tesseract OCR | https://github.com/tesseract-ocr/tesseract |

---

## Troubleshooting

### "Port 5432 already in use"
You have PostgreSQL running locally. Stop it:
```bash
# Mac
brew services stop postgresql

# Ubuntu
sudo systemctl stop postgresql

# Windows
net stop postgresql-x64-16
```

### "Port 3000 already in use"
Change frontend port in `docker-compose.yml`:
```yaml
frontend:
  ports:
    - "3001:80"   # change 3000 to 3001
```

### "OpenAI API key invalid"
Check your `.env` file — make sure `OPENAI_API_KEY` starts with `sk-`

### PDF upload stuck on "Processing"
Large scanned PDFs can take 5–10 minutes for OCR. Check worker logs:
```bash
docker-compose logs -f worker
```

### "Taxonomy not found" on first start
The seed script may have run before the DB was ready. Fix:
```bash
docker-compose exec backend python scripts/seed_taxonomy.py
```

### Backend can't connect to PostgreSQL
Ensure the `DATABASE_URL` in `.env` matches your PostgreSQL credentials.
For Docker, it should be:
```
DATABASE_URL=postgresql+asyncpg://upsc_user:your_password@postgres:5432/upsc_db
```

### Reset and start fresh
```bash
docker-compose down -v   # deletes all data
docker-compose up --build
```

---

## File Storage

All uploaded files are stored in:
```
upsc_intelligence/
└── storage/          ← mounted as Docker volume
    ├── pdfs/
    │   ├── pyqs/
    │   ├── ncerts/
    │   ├── books/
    │   ├── notes/
    │   └── syllabus/
    ├── images/       ← extracted from PDFs, AI-captioned
    ├── newspapers/
    └── temp/
```

This survives `docker-compose down` but is deleted by `docker-compose down -v`.

To back up your data:
```bash
# Mac/Linux
cp -r storage/ ~/upsc_backup_$(date +%Y%m%d)/

# Windows (PowerShell)
Copy-Item -Recurse storage\ "$env:USERPROFILE\upsc_backup_$(Get-Date -Format yyyyMMdd)\"
```

---

## Adding More Topics to the Taxonomy

Edit `backend/scripts/seed_taxonomy.py` — add entries to the `TAXONOMY` list,
then re-run:

```bash
# Docker
docker-compose exec backend python scripts/seed_taxonomy.py

# Local
cd backend && python scripts/seed_taxonomy.py
```

---

## API Endpoints Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | System health check |
| `POST` | `/upload/pdf` | Upload any document (PYQ, NCERT, book, notes) |
| `POST` | `/upload/newspaper` | Upload newspaper PDF |
| `POST` | `/upload/json` | Upload PYQ JSON |
| `GET` | `/upload/status/{id}` | Track processing status |
| `GET` | `/upload/documents` | List all uploaded documents |
| `POST` | `/query/` | Ask a question (RAG-powered) |
| `POST` | `/query/answer` | Generate mains answer |
| `POST` | `/query/probable-questions` | Generate probable questions |
| `GET` | `/query/current-affairs` | Browse current affairs |
| `POST` | `/query/conversation/start` | Start new conversation |
| `GET` | `/query/conversation/{id}` | Get conversation history |
| `GET` | `/analytics/weakness` | Gap analysis |
| `GET` | `/analytics/pyq-trends` | PYQ pattern analysis |
| `GET` | `/analytics/ca-summary` | CA topic distribution |
| `GET` | `/analytics/coverage` | Topic coverage scores |
| `GET` | `/revision/weekly` | Weekly cheat sheet |
| `GET` | `/revision/monthly` | Monthly cheat sheet |
| `POST` | `/revision/topic` | Topic-specific revision |
| `GET` | `/revision/history` | Revision log |
| `GET` | `/visuals/document/{id}` | Get visuals for a document |
| `POST` | `/visuals/{id}/process` | Trigger AI captioning |

Full interactive docs at: http://localhost:8000/docs

---

## Production Deployment

For a cloud deployment (e.g., on a VPS like DigitalOcean, Hetzner, or AWS EC2):

1. Set `APP_ENV=production` and `DEBUG=false` in `.env`
2. Set a **strong** `POSTGRES_PASSWORD` and `SECRET_KEY`
3. Point a domain to your server IP
4. Run standard infrastructure via `docker-compose up -d --build` (which uses internal Nginx logic)
   *- OR -* 
   Use **Monolithic Server Deployment**: Build the compiled app internally (`npm run build`), spin down frontend Nginx containers, and reverse proxy directly against the FastAPI `8000` port where `/api/` routing and React assets are completely hybridized into a single stream.
5. Use `certbot` for HTTPS (free SSL reverse proxy forwarding)
6. Consider adding a `watchtower` container for auto-updates

---

## System Requirements

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 4 GB | 8 GB |
| Storage | 10 GB free | 50 GB (for full document library) |
| CPU | 2 cores | 4 cores |
| Internet | Required (OpenAI API) | Stable broadband |
| OS | Windows 10+, macOS, Linux | Any with Docker support |

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Tests cover: models, upload API, ingestion pipeline, query API.

---

*Built for serious UPSC preparation — your personal intelligence engine.*
