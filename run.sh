#!/bin/bash
# BD Pipeline Agent - One-command startup
# Usage: bash run.sh

set -e

echo "=== BD Pipeline Agent ==="
echo ""

# Install dependencies
echo "[1/3] Installing dependencies..."
pip3 install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt --quiet

# Copy .env if not exists
if [ ! -f .env ]; then
  echo "[2/3] Creating .env from template..."
  cp .env.example .env
  echo "     Edit .env to add your API keys (optional for basic operation)"
else
  echo "[2/3] .env already exists"
fi

# Start server
echo "[3/3] Starting server..."
echo ""
echo "  Dashboard: http://localhost:8000"
echo "  API docs:  http://localhost:8000/docs"
echo ""

python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
