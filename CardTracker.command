#!/bin/bash
# Sports Card Tracker — double-click to update and launch the app.
# Works from anywhere (Dock, Desktop) because it points at the install folder.

REPO="$HOME/CardTracker"

if [ ! -d "$REPO/cardtracker" ]; then
  echo "Card Tracker is not installed on this Mac yet (looked in $REPO)."
  echo "Ask Claude to walk you through the one-time install on this computer,"
  echo "then use this shortcut again."
  echo ""
  echo "Press Return to close."
  read -r _
  exit 1
fi

cd "$REPO" || exit 1

echo "=== Sports Card Tracker ==="
echo "Checking for updates..."
git pull --ff-only 2>/dev/null || echo "(Couldn't check for updates right now — launching the current version.)"
echo ""

# If auto-start is on, the app already runs in the background. Just restart that
# service so it picks up the update, instead of starting a second copy.
PLIST="$HOME/Library/LaunchAgents/com.cardtracker.plist"
if [ -f "$PLIST" ]; then
  echo "Auto-start is on — applying the update and restarting the background app..."
  launchctl kickstart -k "gui/$(id -u)/com.cardtracker" 2>/dev/null \
    || { launchctl unload "$PLIST" 2>/dev/null; launchctl load "$PLIST"; }
  sleep 2
  open "http://localhost:8001" 2>/dev/null || true
  echo ""
  echo "Done. The app is up to date and running at http://localhost:8001"
  echo "Press Return to close."
  read -r _
  exit 0
fi

exec bash cardtracker/run.sh
