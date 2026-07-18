#!/bin/bash
# Builds a real macOS app tile on your Desktop: "BD Pipeline.app" with a custom
# icon. Double-clicking it loads your data, starts the app, and opens the
# dashboard. Run this once from inside your PipelineBuild folder:
#
#     bash make_desktop_app.sh

set -e

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER="$REPO/Launch_BD_Pipeline.command"
ICON_SRC="$REPO/assets/bd_icon.png"
APP="$HOME/Desktop/BD Pipeline.app"

if [ ! -f "$LAUNCHER" ]; then
  echo "ERROR: Launch_BD_Pipeline.command not found in $REPO"
  echo "Run 'git pull origin claude/sweet-bardeen-q8zsf1' first, then try again."
  exit 1
fi
chmod +x "$LAUNCHER"

echo "Building the app tile from: $REPO"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# --- executable that runs the launcher ---
cat > "$APP/Contents/MacOS/bdpipeline" <<EOF
#!/bin/bash
exec "$LAUNCHER"
EOF
chmod +x "$APP/Contents/MacOS/bdpipeline"

# --- Info.plist ---
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>BD Pipeline</string>
  <key>CFBundleDisplayName</key><string>BD Pipeline</string>
  <key>CFBundleIdentifier</key><string>com.vinsational.bdpipeline</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>bdpipeline</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSUIElement</key><false/>
</dict></plist>
PLIST

# --- custom icon: PNG -> .icns using built-in macOS tools ---
if [ -f "$ICON_SRC" ] && command -v iconutil >/dev/null 2>&1; then
  ICONSET="$(mktemp -d)/AppIcon.iconset"
  mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s        "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}.png"    >/dev/null
    sips -z $((s*2)) $((s*2)) "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
  echo "Custom icon applied."
else
  echo "Note: icon tools not found; app will use a default icon."
fi

# --- nudge Finder to show the new icon ---
touch "$APP"
/usr/bin/touch "$HOME/Desktop"
killall Finder >/dev/null 2>&1 || true

echo ""
echo "Done. 'BD Pipeline' is now on your Desktop with its own icon."
echo "Double-click it to start. (First time: right-click the app -> Open -> Open.)"
