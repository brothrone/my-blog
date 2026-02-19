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

  # -auto-orient: EXIF 회전 자동 반영
  # -resize: 가로 1200px 초과 시만 축소
  magick "$FILE" -auto-orient -resize "${MAX_WIDTH}x>" -quality $QUALITY "$WEBP_FILE" 2>/dev/null
  echo "변환: $WEBP_FILE"

  NEW_SIZE=$(wc -c < "$WEBP_FILE")
  echo "  절감: $(( (ORIG_SIZE - NEW_SIZE) / 1024 ))KB"
done

echo ""
echo "=== front matter 경로 업데이트 ==="

find "$POSTS_DIR" -name "*.md" | while read -r MD; do
  if grep -q "^image:.*\.\(jpeg\|jpg\|png\)" "$MD"; then
    sed -i '' \
      -e 's|\(^image:.*\)\.jpeg|\1.webp|g' \
      -e 's|\(^image:.*\)\.jpg|\1.webp|g' \
      -e 's|\(^image:.*\)\.png|\1.webp|g' \
      "$MD"
    echo "업데이트: $MD"
  fi
done

echo "=== 완료! ==="
