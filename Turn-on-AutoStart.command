#!/bin/bash
# Card Tracker — double-click to make the app start automatically at login
# and restart itself if it ever stops. macOS only.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"          # repo root (folder this file is in)
RUN_SH="$DIR/cardtracker/run.sh"
WORKDIR="$DIR/cardtracker"
LABEL="com.cardtracker"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/CardTrackerData/server.log"

echo "=== Card Tracker — turn on auto-start ==="
echo ""

if [ ! -f "$RUN_SH" ]; then
  echo "Couldn't find the app at: $RUN_SH"
  echo "Make sure this file is inside your CardTracker folder, then try again."
  echo ""; echo "Press Return to close."; read -r _; exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/CardTrackerData"

# Stop any manually-running copy so the service can grab port 8001
pkill -f "uvicorn app.main:app" 2>/dev/null || true

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$RUN_SH</string>
  </array>
  <key>WorkingDirectory</key><string>$WORKDIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CARD_NO_BROWSER</key><string>1</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_EOF

# (Re)load it
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✅ Auto-start is ON."
echo ""
echo "Card Tracker now launches by itself when you log in, and restarts"
echo "automatically if it ever stops. You can close this window."
echo ""
echo "  • Open the app:   http://localhost:8001  (or from your phones via Tailscale)"
echo "  • Log file:       $LOG"
echo "  • To get updates: double-click 'CardTracker' as usual."
echo "  • To turn this off: double-click 'Turn-off-AutoStart.command'."
echo ""
sleep 2
open "http://localhost:8001" 2>/dev/null || true
echo "Press Return to close."; read -r _
