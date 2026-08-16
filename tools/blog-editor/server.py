#!/usr/bin/env python3
"""
Brothrone Travel — 로컬 블로그 글쓰기 앱

의존성 없음 (Python 표준 라이브러리 + ImageMagick만 사용).
실행:  ./blog-editor       (저장소 루트에서)
"""

import base64
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BLOG = APP_DIR.parent.parent
WORK = BLOG / ".blog-editor"
STAGING = WORK / "staging"
THUMBS = WORK / "thumbs"
DRAFT = WORK / "draft.json"

PORT = int(os.environ.get("BLOG_EDITOR_PORT", "4567"))
QUALITY = 82
MAX_WIDTH = 1200

# ─────────────────────────────────────────────────────────────
# 블로그 규칙 (CLAUDE.md 기준)
# ─────────────────────────────────────────────────────────────

CATEGORIES = {
    "hotel-review": {
        "ko": "숙박후기", "prefix": "[숙박후기]",
        "tags_ko": ["숙박후기"], "tags_en": ["Hotel Review"],
    },
    "airline-review": {
        "ko": "항공리뷰", "prefix": "[항공리뷰]",
        "tags_ko": ["항공"], "tags_en": ["Airline Review"],
    },
    "travel": {
        "ko": "여행후기", "prefix": "[여행후기]",
        "tags_ko": ["여행"], "tags_en": ["Travel"],
    },
    "tips": {
        "ko": "꿀팁", "prefix": "[꿀팁]",
        "tags_ko": ["여행팁"], "tags_en": ["Travel Tips"],
    },
}

# 사진 라벨 프리셋: (파일명, 한글 표시, 기본 alt)
LABEL_PRESETS = {
    "hotel-review": [
        ("exterior", "외관"), ("checkin", "체크인"), ("lobby", "로비"),
        ("room", "객실"), ("bath", "욕실"), ("onsen", "온천"),
        ("breakfast", "조식"), ("dinner", "저녁"), ("lounge", "라운지"),
        ("kitchen", "주방"), ("pool", "수영장"), ("view", "뷰"),
        ("outside", "주변"), ("restaurant", "맛집"), ("amenity", "어메니티"),
    ],
    "airline-review": [
        ("gate", "탑승구"), ("lounge", "라운지"), ("boarding", "탑승"),
        ("seat", "좌석"), ("cabin", "기내"), ("meal", "기내식"),
        ("snack", "간식"), ("drink", "음료"), ("ife", "엔터테인먼트"),
        ("lavatory", "화장실"), ("amenity", "어메니티"),
        ("window", "창밖"), ("arrival", "도착"),
    ],
    "travel": [
        ("view", "풍경"), ("street", "거리"), ("food", "음식"),
        ("cafe", "카페"), ("spot", "명소"), ("transport", "교통"),
        ("hotel", "숙소"), ("night", "야경"), ("map", "지도"),
    ],
    "tips": [
        ("screen", "화면"), ("step", "단계"), ("form", "양식"),
        ("result", "결과"), ("app", "앱"), ("site", "사이트"),
    ],
}

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".JPG", ".JPEG", ".PNG"}


# ─────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9가-힣\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def safe_name(text: str) -> str:
    """파일명으로 쓸 수 있게 정리 (영문 소문자 + 숫자 + 언더스코어)"""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9_-]", "_", text)
    return re.sub(r"_+", "_", text).strip("_") or "photo"


def run(cmd, cwd=BLOG):
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def find_existing(slug: str) -> list[Path]:
    """같은 슬러그를 쓰는 글 파일을 모두 찾는다 (날짜가 달라도 URL이 겹치므로)"""
    hits = []
    for base in (BLOG / "_posts", BLOG / "_en_posts"):
        if not base.exists():
            continue
        for md in base.rglob("*.md"):
            m = re.match(r"^\d{4}-\d{2}-\d{2}-(.+)\.md$", md.name)
            if m and m.group(1).removesuffix("-en") == slug:
                hits.append(md)
    return sorted(hits)


def existing_slugs():
    out = []
    for base, suffix in ((BLOG / "_posts", ""), (BLOG / "_en_posts", "-en")):
        if not base.exists():
            continue
        for md in base.rglob("*.md"):
            m = re.match(r"^\d{4}-\d{2}-\d{2}-(.+)\.md$", md.name)
            if m:
                out.append(m.group(1).removesuffix("-en"))
    return sorted(set(out))


def convert_image(src: Path, dst: Path) -> tuple[bool, str]:
    """WebP 변환 (기존 convert_to_webp.sh와 동일한 설정)"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".webp":
        # 이미 WebP — 재인코딩하면 화질만 손해라 이름만 바꾼다
        if src.resolve() == dst.resolve():
            return True, f"그대로 사용: {dst.name}"
        shutil.move(str(src), str(dst))
        return True, f"{src.name} → {dst.name} (이름만 변경)"
    code, out = run([
        "magick", str(src), "-auto-orient",
        "-resize", f"{MAX_WIDTH}x>", "-quality", str(QUALITY), str(dst),
    ])
    if code != 0 or not dst.exists():
        return False, f"변환 실패: {src.name} — {out.strip()[:200]}"
    saved = (src.stat().st_size - dst.stat().st_size) // 1024
    return True, f"{src.name} → {dst.name} ({saved}KB 절감)"


def make_thumb(src: Path) -> Path:
    THUMBS.mkdir(parents=True, exist_ok=True)
    key = safe_name(str(src).replace("/", "_"))[-80:]
    thumb = THUMBS / f"{key}.jpg"
    if thumb.exists() and thumb.stat().st_mtime >= src.stat().st_mtime:
        return thumb
    run(["magick", str(src), "-auto-orient", "-resize", "320x320^",
         "-quality", "70", str(thumb)])
    return thumb


# ─────────────────────────────────────────────────────────────
# 프론트매터 생성
# ─────────────────────────────────────────────────────────────

def yaml_str(s: str) -> str:
    return '"' + (s or "").replace('\\', '\\\\').replace('"', '\\"') + '"'


def build_markdown(d: dict, lang: str, hero: str) -> str:
    cat = d["category"]
    slug = d["slug"]
    date = d["date"]  # YYYY-MM-DD
    at = d.get("time") or "10:00:00"
    meta = CATEGORIES[cat]

    if lang == "ko":
        title = d["title_ko"].strip()
        if not title.startswith("["):
            title = f"{meta['prefix']} {title}"
        tags = d.get("tags_ko") or meta["tags_ko"]
        fm = [
            "---",
            "layout: post",
            f"title: {yaml_str(title)}",
            f"date: {date} {at} +0900",
            f"category: {cat}",
            "tags:",
            *[f"  - {t}" for t in tags],
        ]
        if hero:
            fm.append(f"image: {hero}")
        fm += [
            f"description: {yaml_str(d.get('desc_ko', ''))}",
            f"en_permalink: /en/{cat}/{slug}/",
            "---",
        ]
        body = d.get("body_ko", "").strip()
    else:
        tags = d.get("tags_en") or meta["tags_en"]
        fm = [
            "---",
            "layout: en-post",
            f"title: {yaml_str(d['title_en'].strip())}",
            f"date: {date} {at} +0900",
            "lang: en",
            f"kr_permalink: /posts/{slug}/",
            f"category: {cat}",
            "tags:",
            *[f"  - {t}" for t in tags],
        ]
        if hero:
            fm.append(f"image: {hero}")
        fm += [
            f"description: {yaml_str(d.get('desc_en', ''))}",
            f"permalink: /en/{cat}/{slug}/",
            "---",
        ]
        body = d.get("body_en", "").strip()

    return "\n".join(fm) + "\n\n" + body + "\n"


def validate(d: dict) -> list[dict]:
    """CLAUDE.md의 '알려진 이슈'를 발행 전에 잡아낸다"""
    errs = []

    def err(level, msg, code=None):
        errs.append({"level": level, "msg": msg, "code": code})

    if d.get("category") not in CATEGORIES:
        err("error", "카테고리를 선택하세요.")
    if not d.get("slug"):
        err("error", "슬러그(영문 파일명)를 입력하세요.")
    elif not re.fullmatch(r"[a-z0-9][a-z0-9-]*", d["slug"]):
        err("error", "슬러그는 영문 소문자·숫자·하이픈만 쓸 수 있습니다.")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.get("date", "")):
        err("error", "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).")

    # ── 기존 글 보호 ──
    slug, date = d.get("slug"), d.get("date", "")
    if slug:
        hits = find_existing(slug)
        same = [h for h in hits if h.name in (f"{date}-{slug}.md", f"{date}-{slug}-en.md")]
        other = [h for h in hits if h not in same]
        if other:
            names = ", ".join(str(h.relative_to(BLOG)) for h in other)
            err("error",
                f"같은 슬러그를 쓰는 다른 날짜의 글이 있습니다 → {names} · "
                f"발행하면 주소(/posts/{slug}/)가 겹쳐 사이트가 깨집니다. "
                f"슬러그를 바꾸거나 날짜를 그 글에 맞추세요.",
                code="conflict")
        if same and not d.get("overwrite"):
            names = ", ".join(str(h.relative_to(BLOG)) for h in same)
            err("error",
                f"이미 발행된 글입니다 → {names} · 덮어쓰려면 발행 창에서 확인이 필요합니다.",
                code="exists")

    if not d.get("title_ko", "").strip():
        err("error", "한국어 제목이 비어 있습니다.")
    if not d.get("title_en", "").strip():
        err("error", "영어 제목이 비어 있습니다.")
    if not d.get("body_ko", "").strip():
        err("error", "한국어 본문이 비어 있습니다.")
    if not d.get("body_en", "").strip():
        err("warn", "영어 본문이 비어 있습니다. 영문 글 없이 발행됩니다.")

    for key, label, limit in (("desc_ko", "한국어 description", 160),
                              ("desc_en", "영문 description", 160)):
        v = (d.get(key) or "").strip()
        if not v:
            err("warn", f"{label}이 비어 있습니다 (SEO에 불리).")
        elif len(v) > limit:
            err("warn", f"{label}이 {len(v)}자입니다 (권장 {limit}자 이내).")

    photos = d.get("photos") or []
    if photos and not any(p.get("hero") for p in photos):
        err("warn", "대표 이미지(썸네일)가 지정되지 않았습니다.")

    # 본문에서 참조하는데 목록에 없는 이미지
    for body_key, lang in (("body_ko", "한국어"), ("body_en", "영문")):
        for path in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", d.get(body_key) or ""):
            if path.startswith("assets/"):
                err("warn", f"{lang} 본문 이미지 경로에 앞 '/'가 없습니다: {path} (발행 시 자동 수정)")

    return errs


# ─────────────────────────────────────────────────────────────
# 발행
# ─────────────────────────────────────────────────────────────

def resolve_photo_names(photos: list[dict]) -> list[dict]:
    """라벨 → 파일명. 중복이면 뒤에 번호를 붙인다."""
    used = {}
    out = []
    for p in photos:
        base = safe_name(p.get("label") or "photo")
        used[base] = used.get(base, 0) + 1
        name = base if used[base] == 1 else f"{base}{used[base]}"
        q = dict(p)
        q["filename"] = f"{name}.webp"
        out.append(q)
    return out


def publish(d: dict) -> dict:
    log = []
    cat, slug, date = d["category"], d["slug"], d["date"]
    img_dir = BLOG / "assets" / "images" / cat / slug
    web_dir = f"/assets/images/{cat}/{slug}"

    # 1) 사진 변환 + 이름 정리
    photos = resolve_photo_names(d.get("photos") or [])
    hero = ""
    touched = []
    for p in photos:
        src = Path(p["src"])
        if not src.is_absolute():
            src = BLOG / src
        if not src.exists():
            log.append(f"⚠️  원본 없음, 건너뜀: {src.name}")
            continue
        dst = img_dir / p["filename"]
        ok, msg = convert_image(src, dst)
        log.append(("✅ " if ok else "❌ ") + msg)
        if not ok:
            continue
        touched.append(dst)
        # 원본이 저장소 안의 변환 전 파일이면 삭제 (기존 스크립트와 동일 동작)
        if src.exists() and src.resolve() != dst.resolve():
            if src.resolve().is_relative_to(STAGING.resolve()):
                src.unlink()          # 업로드 임시본 — 조용히 정리
            elif src.resolve().is_relative_to((BLOG / "assets").resolve()):
                src.unlink()
                log.append(f"   원본 삭제: {src.name}")
        if p.get("hero"):
            hero = f"{web_dir}/{p['filename']}"

    if not hero and photos:
        hero = f"{web_dir}/{photos[0]['filename']}"

    # 2) 마크다운 작성
    ko_dir = BLOG / "_posts" / cat
    en_dir = BLOG / "_en_posts" / cat
    ko_dir.mkdir(parents=True, exist_ok=True)
    en_dir.mkdir(parents=True, exist_ok=True)
    ko_path = ko_dir / f"{date}-{slug}.md"
    en_path = en_dir / f"{date}-{slug}-en.md"

    written = []
    ko_md = build_markdown(d, "ko", hero)
    ko_md = ko_md.replace("](assets/", "](/assets/")
    ko_path.write_text(ko_md, encoding="utf-8")
    written.append(ko_path)
    log.append(f"✅ 한국어 글: {ko_path.relative_to(BLOG)}")

    if (d.get("body_en") or "").strip():
        en_md = build_markdown(d, "en", hero)
        en_md = en_md.replace("](assets/", "](/assets/")
        en_path.write_text(en_md, encoding="utf-8")
        written.append(en_path)
        log.append(f"✅ 영문 글: {en_path.relative_to(BLOG)}")
    else:
        log.append("⏭  영문 본문이 비어 영문 글은 만들지 않았습니다.")

    # 3) git
    git_log = []
    if d.get("git", True):
        paths = [str(p.relative_to(BLOG)) for p in written]
        # 사진이 없으면 이미지 폴더 자체가 없다 — 없는 경로를 add 하면 git이 실패한다
        if img_dir.exists() and any(img_dir.iterdir()):
            paths.append(str(img_dir.relative_to(BLOG)))
        code, out = run(["git", "add", *paths])
        git_log.append(f"$ git add {' '.join(paths)}\n{out}".strip())
        if code != 0:
            log.append("❌ git add 실패 — 커밋하지 않았습니다 (글 파일은 만들어졌습니다)")
            return {"ok": True, "log": log, "git": "\n\n".join(git_log),
                    "ko_path": str(ko_path.relative_to(BLOG)), "hero": hero}

        title = d.get("title_ko", slug).strip()
        msg = d.get("commit_msg") or f"Add {slug} post ({title})"
        # 경로를 못박아 커밋 — 사용자가 따로 스테이징해 둔 다른 작업이 휩쓸려 들어가지 않게
        code, out = run(["git", "commit", "-m", msg, "--", *paths])
        git_log.append(f"$ git commit -m ... -- {' '.join(paths)}\n{out}".strip())
        if code != 0:
            log.append("⚠️  커밋 실패 (아래 git 로그 확인)")
        else:
            log.append(f"✅ 커밋 완료: {msg}")

            if d.get("push"):
                code, out = run(["git", "push"])
                git_log.append(f"$ git push\n{out}".strip())
                if code == 0:
                    log.append("🚀 푸시 완료 — Cloudflare Pages 자동 배포 시작 (1~2분)")
                else:
                    log.append("❌ 푸시 실패 (아래 git 로그 확인)")
            else:
                log.append("⏸  푸시는 하지 않았습니다 (커밋까지만).")
    else:
        log.append("⏸  git 작업 없이 파일만 만들었습니다.")

    # 발행이 끝난 초안은 지운다 — 남겨두면 다음에 열었을 때 모르고 재발행(덮어쓰기)하게 된다
    DRAFT.unlink(missing_ok=True)

    return {
        "ok": True,
        "log": log,
        "git": "\n\n".join(git_log),
        "ko_path": str(ko_path.relative_to(BLOG)),
        "hero": hero,
        "published": True,
    }


# ─────────────────────────────────────────────────────────────
# HTTP
# ─────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    # ---- GET ----
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)

        if u.path in ("/", "/index.html"):
            html = (APP_DIR / "index.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")

        if u.path == "/api/config":
            return self._send(200, {
                "categories": CATEGORIES,
                "labels": LABEL_PRESETS,
                "slugs": existing_slugs(),
                "today": datetime.now().strftime("%Y-%m-%d"),
                "blog": str(BLOG),
            })

        if u.path == "/api/folder":
            cat = (q.get("category") or [""])[0]
            slug = (q.get("slug") or [""])[0]
            d = BLOG / "assets" / "images" / cat / slug
            if not d.exists():
                return self._send(200, {"images": []})
            items = []
            for f in sorted(d.iterdir()):
                if f.suffix in IMAGE_EXT and not f.name.startswith("."):
                    items.append({
                        "src": str(f.relative_to(BLOG)),
                        "name": f.name,
                        "size": f.stat().st_size,
                        "converted": f.suffix.lower() == ".webp",
                    })
            return self._send(200, {"images": items})

        if u.path == "/api/thumb":
            rel = (q.get("path") or [""])[0]
            src = Path(rel)
            if not src.is_absolute():
                src = BLOG / rel
            try:
                src.resolve().relative_to(BLOG.resolve())
            except ValueError:
                return self._send(403, {"error": "허용되지 않은 경로"})
            if not src.exists():
                return self._send(404, {"error": "없음"})
            t = make_thumb(src)
            if t.exists():
                return self._send(200, t.read_bytes(), "image/jpeg")
            return self._send(404, {"error": "썸네일 생성 실패"})

        if u.path == "/api/draft":
            if DRAFT.exists():
                return self._send(200, json.loads(DRAFT.read_text("utf-8")))
            return self._send(200, {})

        return self._send(404, {"error": "not found"})

    # ---- POST ----
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path == "/api/upload":
                d = self._body()
                STAGING.mkdir(parents=True, exist_ok=True)
                name = safe_name(Path(d["name"]).stem) + Path(d["name"]).suffix
                dest = STAGING / f"{int(time.time()*1000)}_{name}"
                dest.write_bytes(base64.b64decode(d["data"].split(",")[-1]))
                return self._send(200, {"src": str(dest), "name": d["name"]})

            if u.path == "/api/validate":
                return self._send(200, {"issues": validate(self._body())})

            if u.path == "/api/draft":
                WORK.mkdir(parents=True, exist_ok=True)
                DRAFT.write_text(json.dumps(self._body(), ensure_ascii=False),
                                 encoding="utf-8")
                return self._send(200, {"ok": True})

            if u.path == "/api/publish":
                d = self._body()
                issues = validate(d)
                if any(i["level"] == "error" for i in issues):
                    return self._send(400, {"ok": False, "issues": issues})
                return self._send(200, publish(d))

            if u.path == "/api/shutdown":
                threading.Timer(0.3, lambda: os._exit(0)).start()
                return self._send(200, {"ok": True})

        except Exception as e:
            import traceback
            return self._send(500, {"ok": False, "error": str(e),
                                    "trace": traceback.format_exc()[-1500:]})

        return self._send(404, {"error": "not found"})


def main():
    for p in (WORK, STAGING, THUMBS):
        p.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"\n  ✍️   Brothrone Travel 글쓰기 앱")
    print(f"  📂  {BLOG}")
    print(f"  🌐  {url}")
    print(f"\n  종료하려면 Ctrl+C\n")
    if "--no-open" not in os.sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  종료했습니다.\n")


if __name__ == "__main__":
    main()
