#!/bin/bash
# Sports Card Tracker — double-click this file to update and launch the app.
# (Created for a git clone; "git pull" grabs the latest changes each time.)

cd "$(dirname "$0")" || exit 1

echo "=== Sports Card Tracker ==="
echo "Checking for updates..."
git pull --ff-only || echo "(Couldn't check for updates right now — launching the current version.)"
echo ""

exec bash cardtracker/run.sh
