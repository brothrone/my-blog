# 정보 및 뉴스 운영

매일 오전 9시(Asia/Seoul) 이 대화의 자동화에서 공식 발표를 확인한다. 신규 노선, 호텔·공항 운영 변경 등 실제 여행 판단에 유용한 소식만 최대 2건 선별한다. 공식 원문 URL·발표일·적용 기간·대상·조건·확인일을 검증하고 한국어·영어로 작성한다. 중요 사실을 추측하지 않으며 원문을 복제하거나 직접 경험한 것처럼 쓰지 않는다.

승인 전 초안 위치: `.blog-editor/news-drafts/YYYY-MM-DD-slug/{ko.md,en.md,sources.json}`. 공개 글 폴더에 넣지 않는다. 기존 초안 및 게시물과 URL·주제로 중복을 확인한다. 이 경로의 초안은 Editor 임시저장 탭과 별개로 Codex 대화에서 검토한다.

사용자 발행 승인 후 한국어는 `_posts/news/`, 영어는 `_en_posts/news/`에 저장한다. category: news, hidden: true, sitemap: true와 적절한 한·영 레이아웃, description, 상호 언어 링크를 넣는다. hidden은 페이지네이션 제외용이며 검색 차단 설정이 아니다. `_config.yml`의 폴더 기본값도 이를 보장한다.

카테고리 진입: `/categories/` → `/category/news/`, `/en/categories/` → `/en/news/`. 메인 최신 글·목록·내부 검색에서 제외하되 카테고리와 게시물은 사이트맵에 포함한다. 검토 전 자동 발행·push 금지.
