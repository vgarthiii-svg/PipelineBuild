#!/bin/bash
# Background-service entry point (used by the auto-start LaunchAgent).
# Pulls the latest version when possible, then launches the app headless.
# A failed/offline pull is ignored so the app always still starts.

HERE="$(cd "$(dirname "$0")" && pwd)"   # .../CardTracker/cardtracker
( cd "$HERE/.." && git pull --ff-only ) >/dev/null 2>&1 || true
exec bash "$HERE/run.sh"
