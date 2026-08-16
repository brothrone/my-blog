#!/usr/bin/env python3
"""
Brothrone Travel — 로컬 블로그 글쓰기 앱

의존성 없음 (Python 표준 라이브러리 + ImageMagick만 사용).
실행:  ./blog-editor       (저장소 루트에서)
"""

# 앱은 시스템 파이썬(3.9)으로 실행된다. 3.10+ 문법의 타입 표기(Path | None 등)를
# 그대로 쓰면 거기서 죽으므로, 표기를 실행 시점에 평가하지 않게 한다.
from __future__ import annotations

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

# 본문 뼈대. 지어낸 게 아니라 기존 글에서 실제로 쓰던 순서를 뽑은 것이다.
#   호텔  예약·가격 → 위치 → 체크인 → 객실 → 욕실 → 조식 → 총평
#   료칸  가는 길 → 체크인 → 객실 → 노천탕 → 가이세키 → 총평
#   항공  출발 공항 → 탑승 → 좌석 → 기내식 → 도착 공항 → 총평
TEMPLATES = {
    "hotel-review": [
        {"name": "호텔",
         "ko": ["예약 및 가격", "위치 및 접근성", "체크인", "객실", "욕실",
                "조식", "주변 환경", "총평"],
         "en": ["Booking & Price", "Location & Access", "Check-in", "Room",
                "Bathroom", "Breakfast", "Neighborhood", "Verdict"]},
        {"name": "료칸·온천",
         "ko": ["예약 및 가격", "가는 길", "체크인", "객실", "노천탕",
                "석식 가이세키", "조식", "총평"],
         "en": ["Booking & Price", "Getting There", "Check-in", "Room",
                "Open-air Bath", "Kaiseki Dinner", "Breakfast", "Verdict"]},
        {"name": "게스트하우스",
         "ko": ["예약 및 가격", "위치", "체크인", "객실", "공용 공간",
                "주변 환경", "총평"],
         "en": ["Booking & Price", "Location", "Check-in", "Room",
                "Shared Spaces", "Neighborhood", "Verdict"]},
    ],
    "airline-review": [
        {"name": "탑승기",
         "ko": ["출발 공항", "탑승", "좌석", "기내식", "기내 시설",
                "도착 공항", "총평"],
         "en": ["Departure Airport", "Boarding", "Seat", "Meal",
                "Cabin & Amenities", "Arrival Airport", "Verdict"]},
        {"name": "공항 라운지",
         "ko": ["위치", "운영 시간", "입장 조건", "라운지 내부", "음식",
                "총평"],
         "en": ["Location", "Opening Hours", "Access", "Inside",
                "Food", "Verdict"]},
    ],
    "travel": [
        {"name": "명소·관람",
         "ko": ["가는 길", "입장 및 요금", "둘러보기", "주변 볼거리", "총평"],
         "en": ["Getting There", "Tickets & Price", "What to See",
                "Nearby", "Verdict"]},
        {"name": "일정 정리",
         "ko": ["일정 한눈에 보기", "1일차", "2일차", "3일차", "경비 정리",
                "총평"],
         "en": ["Itinerary at a Glance", "Day 1", "Day 2", "Day 3",
                "Budget", "Verdict"]},
    ],
    "tips": [
        {"name": "따라하기",
         "ko": ["이게 뭔가요?", "준비물", "단계별 방법", "주의할 점", "정리"],
         "en": ["What Is It?", "What You Need", "Step by Step",
                "Watch Out For", "Summary"]},
        {"name": "정보 정리",
         "ko": ["한눈에 보기", "자세한 내용", "비교", "자주 묻는 질문", "정리"],
         "en": ["At a Glance", "Details", "Comparison", "FAQ", "Summary"]},
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


def run(cmd, cwd=BLOG, stdin=None):
    # stdin 을 명시적으로 닫는다. 안 그러면 입력을 기다리는 명령이 그대로 멈춰버린다.
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       input=(stdin if stdin is not None else ""), timeout=60)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def parse_front(text: str):
    """프론트매터를 갈라낸다. 이 블로그가 쓰는 단순한 형태만 다룬다."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    raw, body = text[3:end].strip("\n"), text[end + 4:].lstrip("\n")

    fm, key = {}, None
    for line in raw.split("\n"):
        if re.match(r"^\s+-\s", line):                 # tags 같은 목록 항목
            if key:
                fm.setdefault(key, [])
                if isinstance(fm[key], list):
                    fm[key].append(line.strip()[1:].strip())
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            fm[key] = []
        else:
            if len(val) > 1 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            fm[key] = val
    return fm, body


def post_files(slug: str, date: str, cat: str):
    return (BLOG / "_posts" / cat / f"{date}-{slug}.md",
            BLOG / "_en_posts" / cat / f"{date}-{slug}-en.md")


def list_posts():
    out = []
    base = BLOG / "_posts"
    if not base.exists():
        return out
    for md in base.rglob("*.md"):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$", md.name)
        if not m:
            continue
        date, slug = m.group(1), m.group(2)
        cat = md.parent.name
        try:
            fm, _ = parse_front(md.read_text(encoding="utf-8"))
        except Exception:
            fm = {}
        _, en = post_files(slug, date, cat)
        out.append({
            "slug": slug, "date": date, "category": cat,
            "title": fm.get("title", slug),
            "image": fm.get("image", ""),
            "tags": fm.get("tags", []) if isinstance(fm.get("tags"), list) else [],
            "has_en": en.exists(),
            "path": str(md.relative_to(BLOG)),
        })
    out.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return out


def all_tags():
    """기존 글에서 쓰던 태그. 표기가 갈리지 않도록 입력할 때 제안한다."""
    ko, en = {}, {}
    for base, bag in ((BLOG / "_posts", ko), (BLOG / "_en_posts", en)):
        if not base.exists():
            continue
        for md in base.rglob("*.md"):
            try:
                fm, _ = parse_front(md.read_text(encoding="utf-8"))
            except Exception:
                continue
            for t in (fm.get("tags") or []):
                if isinstance(t, str) and t:
                    bag[t] = bag.get(t, 0) + 1
    top = lambda d: [k for k, _ in sorted(d.items(), key=lambda x: -x[1])]
    return {"ko": top(ko), "en": top(en)}


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


NOTES = WORK / "notes"


def write_notes(d: dict) -> Path:
    """사진별 메모를 사람이 읽는 형태로 저장한다.

    이 파일을 Claude 가 읽고 본문을 쓴다. 그래서 기계용 JSON 이 아니라
    그대로 읽히는 마크다운으로 남긴다.
    """
    NOTES.mkdir(parents=True, exist_ok=True)
    slug = d.get("slug") or "untitled"
    cat = d.get("category", "")
    cat_ko = CATEGORIES.get(cat, {}).get("ko", cat)
    info = d.get("info") or {}
    photos = d.get("photos") or []

    L = [f"# 메모 — {slug}",
         f"분류: {cat_ko} ({cat}) · 날짜: {d.get('date','')}",
         "",
         "## 글 정보"]
    for key, label in (("title", "제목(가제)"), ("basic", "기본 정보"),
                       ("place", "위치"), ("good", "좋았던 점"),
                       ("bad", "아쉬웠던 점"), ("etc", "그 밖에")):
        v = (info.get(key) or "").strip()
        if v:
            L.append(f"- {label}: {v}")
    if len(L) == 4:
        L.append("- (아직 안 적음)")

    L += ["", f"## 사진 ({len(photos)}장)"]
    for i, p in enumerate(photos, 1):
        head = f"### {i}. {p.get('name','')}"
        if p.get("label"):
            head += f" → {p['label']}"
        if p.get("hero"):
            head += "  ⭐대표"
        L.append(head)
        L.append((p.get("memo") or "").strip() or "(메모 없음)")
        L.append("")

    out = NOTES / f"{slug}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    (NOTES / f"{slug}.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# ─────────────────────────────────────────────────────────────
# 워터마크
# ─────────────────────────────────────────────────────────────

WATERMARK_TEXT = "© Brothrone"
WM_RATIO = 0.26      # 사진 가로폭 대비 워터마크 폭
WM_OPACITY = 0.9


def watermark_asset() -> Path | None:
    """글자 + 그림자 PNG. 한 번 만들어 두고 재사용한다.

    magick 에 폰트 지원이 없어 글자는 Swift(AppKit)로 그린다.
    그림자를 넣는 이유는 밝은 배경(흰 침구·하늘)에서 글자가 묻히기 때문.
    """
    wm = WORK / "watermark.png"
    if wm.exists():
        return wm
    if not shutil.which("swift"):
        return None
    raw = WORK / "watermark-raw.png"
    code, _ = run(["swift", str(APP_DIR / "make-text.swift"),
                   str(raw), WATERMARK_TEXT, "46"])
    if code != 0 or not raw.exists():
        return None
    code, _ = run(["magick", str(raw),
                   "(", "+clone", "-background", "black", "-shadow", "90x4+0+2", ")",
                   "+swap", "-background", "none", "-layers", "merge", "+repage",
                   str(wm)])
    raw.unlink(missing_ok=True)
    return wm if wm.exists() else None


def stamp(dst: Path) -> str:
    """이미 변환된 사진 위에 워터마크를 얹는다."""
    wm = watermark_asset()
    if not wm:
        return "  ⚠️ 워터마크 생략 (글자를 그릴 수 없음)"
    code, out = run(["magick", "identify", "-format", "%w", str(dst)])
    try:
        w = int(out.strip())
    except ValueError:
        return "  ⚠️ 워터마크 생략 (크기 확인 실패)"
    code, out = run([
        "magick", str(dst),
        "(", str(wm), "-resize", f"{max(110, int(w * WM_RATIO))}x",
        "-alpha", "set", "-channel", "A",
        "-evaluate", "multiply", str(WM_OPACITY), "+channel", ")",
        "-gravity", "southeast",
        "-geometry", f"+{max(14, int(w * 0.022))}+{max(12, int(w * 0.017))}",
        "-composite", "-quality", str(QUALITY), str(dst),
    ])
    return "  🔖 워터마크 넣음" if code == 0 else f"  ⚠️ 워터마크 실패: {out.strip()[:120]}"


def convert_image(src: Path, dst: Path, mark: bool = True) -> tuple[bool, str]:
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
    note = stamp(dst) if mark else ""
    saved = (src.stat().st_size - dst.stat().st_size) // 1024
    return True, f"{src.name} → {dst.name} ({saved}KB 절감)" + ("\n" + note if note else "")


def make_thumb(src: Path, w: int = 320) -> Path:
    """미리보기 이미지. 쓰임새에 따라 크기를 나눈다.

    목록·메모는 작게(320) 빠르게, 편집기 본문은 크게(1200) — 본문에서는 사진을
    640px 폭으로 펼쳐 보여주는데, 레티나 화면이면 1280px 가 필요해서
    작은 썸네일을 쓰면 네 배로 늘어나 뭉개져 보인다.
    """
    THUMBS.mkdir(parents=True, exist_ok=True)
    key = safe_name(str(src).replace("/", "_"))[-80:]
    thumb = THUMBS / f"{key}_{w}.jpg"
    if thumb.exists() and thumb.stat().st_mtime >= src.stat().st_mtime:
        return thumb
    if w >= 800:                       # 실제 업로드본과 같은 방식으로 줄인다
        size, q = f"{w}x>", "82"
    else:                              # 목록용은 정사각형에 맞춰 채운다
        size, q = f"{w}x{w}^", "70"
    run(["magick", str(src), "-auto-orient", "-resize", size, "-quality", q, str(thumb)])
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

    # 설명 없는 사진은 검색에 안 잡힌다
    for body_key, lang in (("body_ko", "한국어"), ("body_en", "영문")):
        blank = len(re.findall(r"!\[\s*\]\(", d.get(body_key) or "")) \
              + len(re.findall(r'<img [^>]*alt=""', d.get(body_key) or ""))
        if blank:
            err("warn", f"{lang} 본문에 설명 없는 사진이 {blank}장 있습니다 "
                        f"(사진 아래 설명을 넣으면 검색 노출에 도움이 됩니다).")

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
    touched_dirs = set()
    for p in photos:
        src = Path(p["src"])
        if not src.is_absolute():
            src = BLOG / src
        # 기존 글을 고칠 때는 사진이 원래 있던 폴더를 그대로 쓴다.
        # 슬러그와 폴더 이름이 다른 글이 있어서, 옮기면 사이트의 이미지 주소가 바뀐다.
        pdir = (p.get("dir") or web_dir).lstrip("/")
        dst = BLOG / pdir / p["filename"]
        if not src.exists():
            if dst.exists():          # 이미 자리에 있는 사진 (수정 중인 글)
                touched_dirs.add(dst.parent)
                if p.get("hero"):
                    hero = "/" + str(dst.relative_to(BLOG))
                continue
            log.append(f"⚠️  원본 없음, 건너뜀: {src.name}")
            continue
        ok, msg = convert_image(src, dst, mark=d.get("watermark", True))
        log.append(("✅ " if ok else "❌ ") + msg)
        if not ok:
            continue
        touched_dirs.add(dst.parent)
        # 원본이 저장소 안의 변환 전 파일이면 삭제 (기존 스크립트와 동일 동작)
        if src.exists() and src.resolve() != dst.resolve():
            if src.resolve().is_relative_to(STAGING.resolve()):
                src.unlink()          # 업로드 임시본 — 조용히 정리
            elif src.resolve().is_relative_to((BLOG / "assets").resolve()):
                src.unlink()
                log.append(f"   원본 삭제: {src.name}")
        if p.get("hero"):
            hero = "/" + str(dst.relative_to(BLOG))

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
        for dd in sorted(touched_dirs):
            if dd.exists() and any(dd.iterdir()):
                paths.append(str(dd.relative_to(BLOG)))
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
    def log_message(self, fmt, *a):
        if os.environ.get("BLOG_EDITOR_TRACE"):
            with open("/tmp/blog-editor-trace.log", "a") as f:
                f.write((fmt % a) + "\n")

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
                "templates": TEMPLATES,
                "slugs": existing_slugs(),
                "today": datetime.now().strftime("%Y-%m-%d"),
                "blog": str(BLOG),
            })

        if u.path == "/api/notes":
            slug = (q.get("slug") or [""])[0]
            f = NOTES / f"{slug}.json"
            if f.exists():
                return self._send(200, json.loads(f.read_text("utf-8")))
            return self._send(200, {})

        if u.path == "/api/tags":
            return self._send(200, all_tags())

        if u.path.startswith("/assets/"):
            f = BLOG / u.path.lstrip("/")
            try:
                f.resolve().relative_to(BLOG.resolve())
            except ValueError:
                return self._send(403, {"error": "허용되지 않은 경로"})
            if not f.is_file():
                return self._send(404, {"error": "없음"})
            ct = {".css": "text/css", ".webp": "image/webp", ".jpg": "image/jpeg",
                  ".jpeg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml",
                  ".js": "application/javascript"}.get(f.suffix.lower(),
                                                       "application/octet-stream")
            return self._send(200, f.read_bytes(), ct)

        if u.path == "/api/posts":
            return self._send(200, {"posts": list_posts()})

        if u.path == "/api/post":
            slug = (q.get("slug") or [""])[0]
            date = (q.get("date") or [""])[0]
            cat = (q.get("category") or [""])[0]
            ko_p, en_p = post_files(slug, date, cat)
            if not ko_p.exists():
                return self._send(404, {"error": "글을 찾을 수 없습니다."})
            out = {}
            for name, p in (("ko", ko_p), ("en", en_p)):
                if not p.exists():
                    out[name] = None
                    continue
                text = p.read_text(encoding="utf-8")
                fm, body = parse_front(text)
                out[name] = {"front": fm, "body": body,
                             "path": str(p.relative_to(BLOG))}
            img_dir = BLOG / "assets" / "images" / cat / slug
            out["images"] = ([str(f.relative_to(BLOG)) for f in sorted(img_dir.iterdir())
                              if f.suffix in IMAGE_EXT and not f.name.startswith(".")]
                             if img_dir.exists() else [])
            return self._send(200, out)

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
            try:
                w = max(80, min(1600, int((q.get("w") or ["320"])[0])))
            except ValueError:
                w = 320
            t = make_thumb(src, w)
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

            if u.path == "/api/notes":
                d = self._body()
                path = write_notes(d)
                return self._send(200, {"ok": True,
                                        "path": str(path.relative_to(BLOG))})

            if u.path == "/api/preview":
                # 사이트와 똑같이 보이도록 Jekyll 이 쓰는 kramdown 으로 직접 변환한다
                md = (self._body().get("markdown") or "")
                # Jekyll 은 GFM 파서를 쓴다. hard_wrap(줄바꿈 → <br>)도 거기서만 동작하므로
                # 사이트와 똑같이 보이려면 파서까지 맞춰야 한다.
                code, out = run(
                    ["ruby", "-rkramdown", "-rkramdown-parser-gfm", "-e",
                     'print Kramdown::Document.new($stdin.read, input: "GFM", '
                     'hard_wrap: true).to_html'],
                    stdin=md)
                if code != 0:      # GFM 파서가 없으면 기본 파서로라도 보여준다
                    code, out = run(
                        ["ruby", "-rkramdown", "-e",
                         'print Kramdown::Document.new($stdin.read).to_html'], stdin=md)
                return self._send(200, {"ok": code == 0, "html": out})

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
