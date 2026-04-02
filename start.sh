#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# UPSC Intelligence System — Quick Start (Docker)
# Run: chmod +x start.sh && ./start.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo ""
echo -e "${BOLD}${CYAN}"
echo "  ██╗   ██╗██████╗ ███████╗ ██████╗"
echo "  ██║   ██║██╔══██╗██╔════╝██╔════╝"
echo "  ██║   ██║██████╔╝███████╗██║     "
echo "  ██║   ██║██╔═══╝ ╚════██║██║     "
echo "  ╚██████╔╝██║     ███████║╚██████╗"
echo "   ╚═════╝ ╚═╝     ╚══════╝ ╚═════╝"
echo -e "${RESET}"
echo -e "${BOLD}  UPSC Intelligence System${RESET}"
echo -e "  Your personal AI study engine"
echo ""

# ── Check Docker ──────────────────────────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found.${RESET}"
    echo "   Install from: https://docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker is not running.${RESET}"
    echo "   Start Docker Desktop and try again."
    exit 1
fi

echo -e "${GREEN}✅ Docker is running${RESET}"

# ── Check .env ────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo ""
    echo -e "${YELLOW}⚠️  No .env file found.${RESET}"
    cp .env.example .env
    echo -e "   Created .env from .env.example"
    echo ""
    echo -e "${BOLD}   ACTION REQUIRED:${RESET}"
    echo "   Open .env and add your OpenAI API key:"
    echo -e "   ${CYAN}OPENAI_API_KEY=sk-your-key-here${RESET}"
    echo ""
    read -p "   Press ENTER after you've added your API key..."
fi

# ── Check API key ─────────────────────────────────────────────────────────────
source .env
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-your-openai-api-key-here" ]; then
    echo -e "${RED}❌ OPENAI_API_KEY not set in .env${RESET}"
    echo "   Get your key from: https://platform.openai.com/api-keys"
    exit 1
fi
echo -e "${GREEN}✅ OpenAI API key found${RESET}"

# ── Start ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}🚀 Starting UPSC Intelligence System...${RESET}"
echo ""

docker-compose up --build -d

echo ""
echo -e "${BOLD}⏳ Waiting for services to be ready...${RESET}"
sleep 10

# Wait for backend health
MAX=30
for i in $(seq 1 $MAX); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        break
    fi
    echo -ne "   Waiting for backend... ${i}/${MAX}\r"
    sleep 3
done
echo ""

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  ✅ UPSC Intelligence System is running!${RESET}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BOLD}Dashboard:${RESET}   ${CYAN}http://localhost:3000${RESET}"
echo -e "  ${BOLD}API Docs:${RESET}    ${CYAN}http://localhost:8000/docs${RESET}"
echo ""
echo -e "  ${BOLD}Next steps:${RESET}"
echo "  1. Open http://localhost:3000"
echo "  2. Upload your PYQ JSON file first"
echo "  3. Upload your PYQ PDFs, NCERTs, and books"
echo "  4. Upload today's newspaper"
echo "  5. Start asking questions!"
echo ""
echo -e "  ${BOLD}To stop:${RESET}     ${CYAN}docker-compose down${RESET}"
echo -e "  ${BOLD}To view logs:${RESET} ${CYAN}docker-compose logs -f backend${RESET}"
echo ""
