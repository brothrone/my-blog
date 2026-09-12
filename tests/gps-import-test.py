"""Regression check on a temporary copy; never rewrites published photographs."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/blog-editor'))
from gps import strip_new_photo_gps
TOOL = ROOT / '.blog-editor/exiftool-runtime/Image-ExifTool-13.55/exiftool'

def metadata(path):
    return json.loads(subprocess.check_output(['/usr/bin/perl',str(TOOL),'-j','-G1','-EXIF:all','-XMP:all',str(path)]))[0]

def image_chunks(path):
    raw=path.read_bytes(); offset=12; chunks=[]
    while offset < len(raw):
        tag=raw[offset:offset+4]; length=struct.unpack('<I',raw[offset+4:offset+8])[0]
        if tag not in (b'EXIF', b'XMP '): chunks.append((tag,raw[offset+8:offset+8+length]))
        offset += 8+length+(length%2)
    return chunks

original=ROOT / 'assets/images/airline-review/dl196/dl196_1.webp'
digest=hashlib.sha256(original.read_bytes()).digest()
with tempfile.TemporaryDirectory() as d:
    new=Path(d)/'new-photo.webp';shutil.copy2(original,new)
    before=metadata(new);chunks=image_chunks(new)
    assert any('GPS' in key for key in before)
    strip_new_photo_gps(new)
    after=metadata(new)
    assert not any('GPS' in key for key in after)
    assert {k:v for k,v in before.items() if 'GPS' not in k} == after
    assert image_chunks(new)==chunks, 'Image data or non-location chunks changed'
    stripped=new.read_bytes();strip_new_photo_gps(new);assert stripped==new.read_bytes()
assert hashlib.sha256(original.read_bytes()).digest()==digest
print('PASS: GPS removed; other EXIF, compressed image bytes, existing original unchanged; repeat safe')
# Exercise both import routes against a temporary blog, including an existing file.
import base64
import server
real_blog,real_staging=server.BLOG,server.STAGING
with tempfile.TemporaryDirectory() as d:
    server.BLOG=Path(d);server.STAGING=Path(d)/'staging'
    folder=Path(d)/'assets/images/hotel-review/test';folder.mkdir(parents=True)
    existing=folder/'photo.webp';existing.write_bytes(original.read_bytes())
    upload={'name':'photo.webp','data':base64.b64encode(original.read_bytes()).decode()}
    replies=[]
    h=object.__new__(server.Handler);h._send=lambda code,body:replies.append((code,body))
    h.path='/api/add-photos';h._body=lambda:{'category':'hotel-review','slug':'test','files':[upload]}
    h.do_POST();assert replies[-1][0]==200,replies[-1]
    new=Path(d)/replies[-1][1]['added'][0];assert new!=existing
    assert not any('GPS' in k for k in metadata(new))
    assert existing.read_bytes()==original.read_bytes()
    h.path='/api/upload';h._body=lambda:upload;h.do_POST()
    assert replies[-1][0]==200,replies[-1]
    assert not any('GPS' in k for k in metadata(Path(replies[-1][1]['src'])))
server.BLOG,server.STAGING=real_blog,real_staging
print('PASS: both upload routes strip new copies only; existing same-name photograph preserved')
