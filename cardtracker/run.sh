#!/bin/bash
# Sports Card Tracker - one-command startup
# Usage: bash cardtracker/run.sh

set -e
cd "$(dirname "$0")"

echo "=== Sports Card Tracker ==="
echo ""

echo "[1/3] Installing dependencies..."
pip3 install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt --quiet

if [ ! -f .env ]; then
  echo "[2/3] Creating .env from template..."
  cp .env.example .env
  echo "      Add your ANTHROPIC_API_KEY to .env to enable photo auto-fill (optional)."
else
  echo "[2/3] .env already exists"
fi

echo "[3/3] Starting server..."
echo ""
echo "  App:      http://localhost:8001"
echo "  API docs: http://localhost:8001/docs"
echo ""
echo "  On your phone: open http://<this-computer-ip>:8001 to scan cards with the camera."
echo ""

python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
