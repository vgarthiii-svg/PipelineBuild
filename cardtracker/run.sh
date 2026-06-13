#!/bin/bash
# Sports Card Tracker - one-command startup
# Usage: bash cardtracker/run.sh
#
# Creates a self-contained virtual environment (.venv) the first time so it
# never touches your system Python, then installs deps and starts the app.

set -e
cd "$(dirname "$0")"

echo "=== Sports Card Tracker ==="
echo ""

# Find a Python 3 interpreter
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "ERROR: Python 3 is not installed."
  echo "  macOS:   brew install python   (or install from https://www.python.org/downloads/)"
  echo "  Windows: install Python 3 from the Microsoft Store or python.org, then re-run."
  exit 1
fi

echo "[1/4] Setting up an isolated environment (.venv)..."
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
# Resolve the venv's python (Unix: bin/, Windows Git Bash: Scripts/)
if [ -x ".venv/bin/python" ]; then
  VENV_PY=".venv/bin/python"
else
  VENV_PY=".venv/Scripts/python.exe"
fi

echo "[2/4] Installing dependencies..."
"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install -r requirements.txt --quiet

if [ ! -f .env ]; then
  echo "[3/4] Creating .env from template..."
  cp .env.example .env
  echo "      Add your ANTHROPIC_API_KEY to .env to enable photo auto-fill (optional)."
else
  echo "[3/4] .env already exists"
fi

URL="http://localhost:8001"
echo "[4/4] Starting server..."
echo ""
echo "  App:      $URL"
echo "  API docs: $URL/docs"
echo ""
echo "  On your phone: open http://<this-computer-ip>:8001 to scan cards with the camera."
echo "  Press Ctrl+C to stop."
echo ""

# Auto-open the app in the default browser a moment after the server starts.
# Skipped when run as a background service (CARD_NO_BROWSER=1).
if [ "${CARD_NO_BROWSER:-0}" != "1" ]; then
( sleep 2
  if command -v open >/dev/null 2>&1; then open "$URL"          # macOS
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" # Linux
  elif command -v powershell.exe >/dev/null 2>&1; then powershell.exe -c "start $URL"  # Windows (WSL/Git Bash)
  fi
) >/dev/null 2>&1 &
fi

exec "$VENV_PY" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
