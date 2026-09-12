"""Remove GPS from newly imported photos without re-encoding image data."""
from pathlib import Path
import shutil
import subprocess


def strip_new_photo_gps(photo: Path) -> None:
    installed = shutil.which('exiftool')
    local = Path(__file__).resolve().parents[2] / '.blog-editor/exiftool-runtime/Image-ExifTool-13.55/exiftool'
    command = [installed] if installed else ['/usr/bin/perl', str(local)]
    if not installed and not local.is_file():
        raise RuntimeError('GPS 제거 도구가 없습니다. ExifTool 설치 후 사진을 다시 추가해주세요.')
    # Target GPS metadata only. Preserve capture dates, orientation, colour profiles,
    # other EXIF/XMP fields and the original compressed image stream.
    result = subprocess.run(command + ['-overwrite_original', '-P', '-GPS:all=', '-XMP-exif:GPS*=', str(photo.resolve())],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('사진의 GPS 제거에 실패했습니다. 파일 형식을 확인해주세요.')
