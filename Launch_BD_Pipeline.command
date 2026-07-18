#!/bin/bash
# BD Pipeline - one-click launcher for Mac.
# Double-click this file to start the app and open the dashboard in your browser.
#
# Placement: keep this file in your PipelineBuild folder and put an ALIAS of it
# on your Desktop (right-click -> Make Alias, then drag the alias to the Desktop).

# --- Find the PipelineBuild folder ---
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$DIR/app/main.py" ]; then
  # Fallback if the launcher was copied elsewhere
  DIR="$HOME/PipelineBuild"
fi
if [ ! -f "$DIR/app/main.py" ]; then
  echo "Could not find the PipelineBuild folder."
  echo "Open this file in a text editor and set DIR to your folder's path."
  echo "Press Return to close."
  read _
  exit 1
fi
cd "$DIR" || exit 1

echo "=== BD Pipeline Agent ==="
echo "Folder: $DIR"
echo ""

URL="http://localhost:8000"

# --- If it's already running, just open the browser ---
if curl -s -o /dev/null "$URL"; then
  echo "App already running. Opening $URL ..."
  open "$URL"
  exit 0
fi

# --- Pick a Python and make sure dependencies are installed ---
PY="python3"
if [ -x "$DIR/.venv/bin/python" ]; then
  PY="$DIR/.venv/bin/python"
fi

if ! "$PY" -c "import uvicorn" 2>/dev/null; then
  echo "First run: installing dependencies (this happens once)..."
  "$PY" -m pip install -r requirements.txt --quiet
fi

# --- Start the server in the background ---
echo "Starting the app..."
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!

# --- Wait until it responds, then open the browser ---
for i in $(seq 1 30); do
  if curl -s -o /dev/null "$URL"; then
    break
  fi
  sleep 0.5
done
echo "Opening $URL ..."
open "$URL"

echo ""
echo "The app is running. Keep this window open while you use it."
echo "To stop the app: close this window, or press Control-C."

# Keep the window attached to the server so closing it stops the app
wait $SERVER_PID
