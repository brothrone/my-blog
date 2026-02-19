#!/bin/bash
IMAGES_DIR="assets/images"
POSTS_DIR="_posts"
QUALITY=82
MAX_WIDTH=1200

echo "=== WebP 변환 시작 (ImageMagick) ==="

find "$IMAGES_DIR" -type f \( -iname "*.jpeg" -o -iname "*.jpg" -o -iname "*.png" \) | while read -r FILE; do
  WEBP_FILE="${FILE%.*}.webp"
  if [ -f "$WEBP_FILE" ]; then
    echo "스킵: $WEBP_FILE"
    continue
  fi
  ORIG_SIZE=$(wc -c < "$FILE")

  magick "$FILE" -auto-orient -resize "${MAX_WIDTH}x>" -quality $QUALITY "$WEBP_FILE" 2>/dev/null
  echo "변환: $WEBP_FILE"

  NEW_SIZE=$(wc -c < "$WEBP_FILE")
  echo "  절감: $(( (ORIG_SIZE - NEW_SIZE) / 1024 ))KB"
done

echo ""
echo "=== front matter 및 본문 경로 업데이트 ==="

find "$POSTS_DIR" -name "*.md" | while read -r MD; do
  sed -i '' \
    -e 's/\.jpeg/.webp/g' \
    -e 's/\.jpg/.webp/g' \
    -e 's/\.png/.webp/g' \
    "$MD"
  echo "업데이트: $MD"
done

echo "=== 완료! ==="
