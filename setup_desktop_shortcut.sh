#!/bin/bash
# Creates a clickable "BD Pipeline" shortcut on your Desktop that launches the app.
# Run this once from inside your PipelineBuild folder:  bash setup_desktop_shortcut.sh

set -e

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER="$REPO/Launch_BD_Pipeline.command"

if [ ! -f "$LAUNCHER" ]; then
  echo "Could not find Launch_BD_Pipeline.command in $REPO"
  echo "Run 'git pull' first, then try again."
  exit 1
fi

chmod +x "$LAUNCHER"

SHORTCUT="$HOME/Desktop/BD Pipeline.command"
cat > "$SHORTCUT" <<EOF
#!/bin/bash
# Desktop shortcut -> BD Pipeline launcher (auto-generated)
exec "$LAUNCHER"
EOF
chmod +x "$SHORTCUT"

echo ""
echo "Done. A 'BD Pipeline' shortcut is now on your Desktop."
echo "Double-click it to start the app and open the dashboard."
echo "(First click only: if macOS warns, right-click the shortcut -> Open -> Open.)"
