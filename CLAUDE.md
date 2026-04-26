# Brothrone Travel Blog — Project Context

## 기본 정보
- **블로그 이름**: Brothrone Travel
- **URL**: https://brothrone.org
- **로컬 경로**: `~/Desktop/my-blog`
- **기술 스택**: Jekyll + Cloudflare Pages (자동 배포), Netlify도 연결됨
- **편집 도구**: Obsidian (Templater 플러그인) + VSCode

## 디렉토리 구조
```
my-blog/
├── _posts/
│   ├── airline-review/
│   ├── hotel-review/
│   └── travel/
├── assets/images/
│   ├── airline-review/{포스트명}/
│   ├── hotel-review/{포스트명}/
│   └── travel/{포스트명}/
└── _config.yml
```

## 카테고리 규칙
- **반드시 `category` 단수 사용** (`categories` 복수 쓰면 카테고리 페이지에 안 잡힘)
- 사용 중인 카테고리: `항공리뷰`, `숙박후기`, `여행`, `항공팁`, `숙박팁`, `여행팁`
- 한국어 / 영어 이중 언어 포스팅 운영

## _config.yml 주요 설정 (적용 완료)
```yaml
kramdown:
  hard_wrap: true  # 엔터 한 번도 줄바꿈 처리

plugins:
  - jekyll-sitemap
```
- Sitemap 제외: 카테고리/태그/페이지네이션 목록 페이지, 네이버 인증 파일

## Front Matter 템플릿

### 항공리뷰
```yaml
---
layout: post
title: "[항공리뷰] "
date: <% tp.date.now("YYYY-MM-DD HH:mm:ss") %> +0900
category: 항공리뷰
tags:
  - 항공
image: /assets/images/airline-review/
---
```

### 숙박후기
```yaml
---
layout: post
title: "[숙박후기] "
date: <% tp.date.now("YYYY-MM-DD HH:mm:ss") %> +0900
category: 숙박후기
tags:
  - 숙박
image: /assets/images/hotel-review/
---
```

### 여행후기
```yaml
---
layout: post
title: "[여행후기] "
date: <% tp.date.now("YYYY-MM-DD HH:mm:ss") %> +0900
category: 여행
tags:
  - 여행
image: /assets/images/travel/
---
```

### 여행팁
```yaml
---
layout: post
title: "[꿀팁] "
date: <% tp.date.now("YYYY-MM-DD HH:mm:ss") %> +0900
category: 여행팁
tags:
  - 여행팁
image: /assets/images/tips/
---
```

## Obsidian 설정 (중요)
- **Wikilinks OFF**: Use [[Wikilinks]] → 비활성화 (Markdown 표준 경로 사용)
- 이미지는 drag & drop → `assets/images/{카테고리}/{포스트명}/` 에 저장
- 이미지 변환: WebP 변환 후 원본(jpeg/png) 자동 삭제

### 이미지 경로 앞 `/` 누락 문제 (convert_to_webp.sh에 추가됨)
```bash
sed -i 's|](assets/|](/assets/|g' "$md_file"
sed -i 's|image: assets/|image: /assets/|g' "$md_file"
```

## 배포 워크플로우
```bash
cd ~/Desktop/my-blog
git add .
git commit -m "Add {포스트명} post"
git push
# → Cloudflare Pages 자동 배포
```

## 알려진 이슈 & 해결법
- **영문 포스트 날짜**: `+0900` timezone 명시 필수 (GitHub Pages 빌드 이슈)
- **파비콘 캐시**: Cloudflare 대시보드에서 캐시 퍼지 + `Cmd+Shift+R` 강력 새로고침
- **줄바꿈 문제**: `_config.yml`에 `hard_wrap: true` 적용으로 해결됨
- **카테고리 미분류**: `category` 단수 확인 (복수형 금지)

## SEO 현황 (2026년 3월 기준)
- 한국어 약 20개 + 영어 약 20개 포스팅
- 평균 게재순위 약 17위 (2페이지) → 1페이지 진입이 목표
- 잘 노출된 키워드: `visit japan web login` (순위 4위)
- 하루 수 명 자연 방문자 유입 중

## 수익화 방향
- 애드센스: 월 방문자 300~500명 이후 신청 권장
- 제휴 프로그램: 부킹닷컴, 호텔스컴바인, 클룩 → 트래픽 기준 없이 즉시 가능 (강력 추천)
