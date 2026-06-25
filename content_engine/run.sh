#!/bin/bash
# Content Creator Engine - one-command startup.
# Usage: bash run.sh   (then open http://localhost:8000)
set -e

cd "$(dirname "$0")/backend"

echo "=== Content Creator Engine ==="
echo "[1/3] Installing dependencies..."
pip3 install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt --quiet

if [ ! -f .env ]; then
  echo "[2/3] Creating .env from template (runs in mock mode until you add keys)..."
  cp .env.example .env
else
  echo "[2/3] .env already exists"
fi

echo "[3/3] Starting server..."
echo ""
echo "  App:      http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo ""
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
