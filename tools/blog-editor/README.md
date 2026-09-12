# Brothrone Editor

## 새 사진의 GPS 제거

Editor의 사진 추가/업로드는 새로 저장한 복사본에만 ExifTool을 실행하여 EXIF GPS와 XMP EXIF GPS 필드를 제거합니다. 기존 폴더의 사진이나 이미 발행된 사진을 일괄 처리하지 않습니다. 이미지 재압축은 하지 않으며 촬영일·색상 프로필 등 다른 메타데이터를 유지합니다.

이 Mac에서는 `.blog-editor/exiftool-runtime/Image-ExifTool-13.55/`의 검증된 공식 ExifTool을 사용합니다. 다른 Mac에서는 `exiftool`을 설치해야 합니다. 도구가 없거나 제거에 실패하면 해당 업로드를 실패 처리합니다.
