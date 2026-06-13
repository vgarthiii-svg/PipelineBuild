#!/bin/bash
# Card Tracker — double-click to stop the app from starting automatically.
# This does NOT delete any data; it just turns auto-start off.

LABEL="com.cardtracker"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "=== Card Tracker — turn off auto-start ==="
echo ""

if [ -f "$PLIST" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "✅ Auto-start is OFF. The app will no longer launch on its own."
  echo "   (Your cards and settings are untouched.)"
  echo "   To run it again, double-click 'CardTracker'."
else
  echo "Auto-start wasn't turned on, so there's nothing to remove."
fi

echo ""
echo "Press Return to close."; read -r _
