#!/bin/bash
# 글쓰기 앱을 맥 애플리케이션(.app)으로 만든다.
#   ./tools/make-app.sh
# 결과: ~/Applications/Brothrone 글쓰기.app  (Spotlight·Launchpad에서 검색됨)
set -e

REPO="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Applications/Brothrone 글쓰기.app"
PORT=4567

# Finder에서 실행하면 PATH가 /usr/bin:/bin 수준으로 좁아져 homebrew 명령을 못 찾는다.
# 그래서 지금 환경에서 찾은 경로를 앱 안에 박아 넣는다.
PYTHON="$(command -v python3 || echo /usr/bin/python3)"
MAGICK="$(command -v magick || true)"
if [ -z "$MAGICK" ]; then
  echo "❌ ImageMagick(magick)이 없습니다. brew install imagemagick 후 다시 실행하세요."
  exit 1
fi
EXTRA_PATH="$(dirname "$MAGICK"):$(dirname "$PYTHON")"

echo "블로그 폴더 : $REPO"
echo "python3     : $PYTHON"
echo "magick      : $MAGICK"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# ── 실행 파일 ─────────────────────────────────────────────────
# swiftc가 있으면 자체 창을 가진 네이티브 앱으로, 없으면 브라우저를 여는 셸 앱으로 만든다.
MODE="shell"
if command -v swiftc >/dev/null 2>&1; then
  echo "빌드 방식    : Swift 네이티브 (자체 창)"
  BUILD="$(mktemp -d)"
  cat > "$BUILD/Cfg.swift" <<EOF
enum Cfg {
    static let repo      = "$REPO"
    static let python    = "$PYTHON"
    static let extraPath = "$EXTRA_PATH"
    static let port      = $PORT
    static let logPath   = "$HOME/Library/Logs/brothrone-editor.log"
}
EOF
  if swiftc -O "$BUILD/Cfg.swift" "$REPO/tools/mac-app/BlogEditor.swift" \
            -o "$APP/Contents/MacOS/launch" 2>"$BUILD/err.txt"; then
    codesign -s - -f "$APP/Contents/MacOS/launch" >/dev/null 2>&1
    MODE="swift"
  else
    echo "⚠️  Swift 빌드 실패 — 셸 방식으로 대체합니다."
    sed 's/^/    /' "$BUILD/err.txt" | head -12
  fi
else
  echo "빌드 방식    : 셸 래퍼 (swiftc 없음)"
fi

if [ "$MODE" = "shell" ]; then
cat > "$APP/Contents/MacOS/launch" <<EOF
#!/bin/bash
REPO="$REPO"
PORT=$PORT
PYTHON="$PYTHON"
export PATH="$EXTRA_PATH:\$PATH"
export LANG="\${LANG:-en_US.UTF-8}"
export LC_ALL="\${LC_ALL:-en_US.UTF-8}"

alert() {
  osascript -e "display alert \"Brothrone 글쓰기\" message \"\$1\" as critical" >/dev/null 2>&1
}

[ -d "\$REPO" ] || { alert "블로그 폴더를 찾을 수 없습니다:\n\$REPO\n\n폴더를 옮겼다면 tools/make-app.sh 를 다시 실행하세요."; exit 1; }
command -v magick >/dev/null 2>&1 || { alert "ImageMagick을 찾을 수 없습니다.\n터미널에서 brew install imagemagick 을 실행한 뒤 tools/make-app.sh 를 다시 실행하세요."; exit 1; }

# 이미 켜져 있으면 창만 다시 연다
if /usr/bin/curl -s -o /dev/null --max-time 1 "http://127.0.0.1:\$PORT/api/config"; then
  open "http://127.0.0.1:\$PORT"
  exit 0
fi

cd "\$REPO" || exit 1
"\$PYTHON" tools/blog-editor/server.py 2>>"\$HOME/Library/Logs/brothrone-editor.log" || {
  alert "글쓰기 앱을 시작하지 못했습니다.\n\n자세한 내용:\n~/Library/Logs/brothrone-editor.log"
  exit 1
}
EOF
fi
chmod +x "$APP/Contents/MacOS/launch"

# ── Info.plist ────────────────────────────────────────────────
cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>              <string>Brothrone 글쓰기</string>
  <key>CFBundleDisplayName</key>       <string>Brothrone 글쓰기</string>
  <key>CFBundleIdentifier</key>        <string>org.brothrone.blogeditor</string>
  <key>CFBundleExecutable</key>        <string>launch</string>
  <key>CFBundleIconFile</key>          <string>icon</string>
  <key>CFBundlePackageType</key>       <string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key>           <string>1</string>
  <key>LSMinimumSystemVersion</key>    <string>11.0</string>
  <key>NSHighResolutionCapable</key>   <true/>
</dict>
</plist>
EOF

# ── 아이콘 ────────────────────────────────────────────────────
# 이 ImageMagick 빌드에는 폰트(FreeType) 지원이 없을 수 있어 글자 대신 도형으로 그린다.
ICONSET="$(mktemp -d)/icon.iconset"
mkdir -p "$ICONSET"
BASE="$(mktemp -d)/base.png"
magick -size 1024x1024 xc:none \
  -fill "#2563eb" -draw "roundrectangle 0,0 1023,1023 210,210" \
  -fill white \
  -draw "polygon 271.6,639.2 384.8,752.4 780.7,356.5 667.5,243.3" \
  -draw "polygon 271.6,639.2 384.8,752.4 243.3,780.7" \
  -fill "#93c5fd" \
  -draw "polygon 667.5,243.3 780.7,356.5 723,414 610,301" \
  "$BASE" 2>/dev/null

if [ -s "$BASE" ]; then
  for s in 16 32 64 128 256 512; do
    magick "$BASE" -resize ${s}x${s}             "$ICONSET/icon_${s}x${s}.png"
    magick "$BASE" -resize $((s*2))x$((s*2))     "$ICONSET/icon_${s}x${s}@2x.png"
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/icon.icns" 2>/dev/null
fi

if [ -s "$APP/Contents/Resources/icon.icns" ]; then
  echo "아이콘        : 생성됨"
else
  echo "⚠️  아이콘 생성 실패 — 기본 아이콘으로 동작합니다 (기능에는 영향 없음)."
fi

touch "$APP"   # Finder 아이콘 캐시 갱신

echo ""
echo "✅ 만들었습니다: $APP"
echo "   Spotlight(⌘Space)에서 '글쓰기' 로 검색하거나,"
echo "   Finder에서 열어 Dock으로 끌어다 두면 됩니다."
