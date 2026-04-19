# Newsroom AI — 기자 액션 UX 확장 요구사항

> 분석·판단까지만 닫혀 있던 루프를 **생성·행동**까지 확장한다.
> 기자가 대시보드에서 본 정보를 복사·공유·초안·트래킹으로 바로 이어갈 수 있게 한다.

---

## 0. 배경

현재 시스템은 수집 → 분석 → 브리핑·의제까지 보여주지만, 기자 관점에서 **다음 단계 행위**로 이어지는 출구가 없다.

| 단계 | 현재 | 개선 후 |
|------|------|---------|
| 정보 수집 | ✓ 자동 (RSS/NewsAPI/Naver) | 유지 |
| AI 분류·의제 | ✓ 자동 (Haiku + Sonnet) | 유지 |
| 기자 판단 | ✓ 대시보드 탐색 | 유지 |
| **복사/공유** | ✗ | **F1, F2** 신규 |
| **초안 작성** | ✗ | **F3** 신규 |
| **이슈 트래킹** | ✗ | **F4** 신규 |

PT 서사의 핵심 세일즈 포인트는 **F3 (AI 기사 초안 생성)** 이다. "AI가 분석만 하는 게 아니라, 기자가 한 번 더 클릭하면 초안까지 만든다."

---

## 1. 기능 상세

### F1. 전역 클립보드 복사 (필수, 공수 낮음)

**진입점 4곳**:

| 위치 | 복사 포맷 |
|------|----------|
| 뉴스 상세 (`/news/[id]`) | `{제목}\n{매체} · {발행일}\n{요약}\n{원문URL}` |
| 브리핑 섹션 카드 | `## {섹션 제목}\n{섹션 본문}` (Markdown) |
| 헤드라인 추천 개별 카드 | `{헤드라인}` (단독 텍스트) |
| 의제 Top 5 카드 | `{rank}. {topic}\n{summary}\n(매체 {source_count}곳 · 기사 {article_count}건)` |

**구현 원칙**:
- `navigator.clipboard.writeText()` 네이티브 API. 외부 의존성 0.
- 버튼은 `lucide-react`의 `Copy` 아이콘 + 툴팁.
- 클릭 시 버튼 라벨 1.2초간 "복사됨 ✓" 로 토글 후 원복.
- 공용 컴포넌트 `<CopyButton value={...} />` 한 개로 4곳 재사용.

**UX 피드백**: 별도 토스트 라이브러리 없이 버튼 라벨 자체 변경만으로 충분. shadcn toast 미설치 상태 유지.

---

### F2. 브리핑 내보내기 (필수)

**PDF 제외** (사용자 결정). 다음 2경로만 지원:

**F2-1. 전체 Markdown 복사**
- 브리핑 페이지(`/reports`) 상단에 "마크다운 전체 복사" 버튼.
- 조립 포맷:
  ```markdown
  # {headline}

  > 생성: {generated_at} · 모델: {model_used}

  {summary}

  ---

  ## {section.title} ({section.category})
  {section.content}

  (섹션 반복)
  ```

**F2-2. 메일로 보내기**
- "메일로 보내기" 버튼 클릭 → `mailto:?subject={encoded headline}&body={encoded MD}`.
- 수신자 미지정 (기자가 메일 클라이언트에서 입력).
- URL 길이 제한(브라우저별 2000~8000자)을 고려해 body는 MD 전체 대신 **headline + summary + 섹션 제목 리스트** 만 포함. 상세 내용은 본문 마지막에 "상세는 사내 대시보드 {URL} 참고" 링크.

---

### F3. AI 기사 초안 생성 (차별화 핵심)

**진입점 3곳**:

| 진입점 | 전달 데이터 | 기자 의도 |
|--------|-----------|----------|
| 뉴스 상세 | `{article_ids: [해당 기사 id]}` | "이 단일 기사 기반으로 속보성 기사 초안" |
| 의제 카드 (대시보드/분석) | `{article_ids: related_article_ids}` | "여러 매체 교차 참조한 종합 기사 초안" |
| 헤드라인 추천 카드 | `{article_ids: 현재 topic의 관련 기사, topic_hint: 선택한 헤드라인}` | "이 제목 방향으로 기사 작성" |

**모달 UX**:
1. 진입점 클릭 → `<DraftDialog>` 열림.
2. 상단에 `style` 선택 (라디오: `straight`/`analysis`/`feature`, 기본 straight).
3. "초안 생성" 버튼 → `POST /drafts/generate` 호출.
4. 로딩 (Sonnet 4.6 응답 대기 ~8-15초, 스피너 + 진행 메시지 "AI가 초안을 작성하고 있습니다...").
5. 응답 표시:
   - **제목 후보 3안** (각각 복사 버튼)
   - **리드 문단**
   - **본문** (Markdown 렌더)
   - **맥락·배경**
   - **6하원칙 자체 점검** (체크리스트 UI — 누락 항목은 붉은색으로 경고)
   - **출처** (매체 이름 + 링크 리스트)
6. 모달 하단에 "전체 Markdown 복사" 버튼.

**LLM 명세**:
- 모델: `claude-sonnet-4-6` (PT 품질 우선).
- 새 프롬프트 `DRAFT_SYSTEM` — 편집국장 페르소나, 역피라미드 강제, 유보적 표현("~로 알려졌다"), 6하원칙 self-check, **원문에 없는 사실 추측 금지**.
- 출력 Pydantic `DraftOut`(후술 API 명세) — 스키마 검증 실패 시 500 반환.

**비용 상한**:
- 초안 1건당 ~$0.05 추정. 데모 사용만 전제, 캐시 미구현.
- 향후 개선 여지: (article_ids + topic_hint) 해시 키로 DB 캐시.

---

### F4. 워치리스트 (차별화, 영속성)

**플로우**:
1. 기자가 `/watchlist` 페이지 or 대시보드 상단 퀵 추가 폼에서 키워드 등록 (예: "호르무즈", "환율", "AI 규제").
2. 스케줄러의 매 수집 사이클마다 분류 완료 분석 건에 대해 활성 키워드 매칭 체크.
3. 매칭 시 SSE 이벤트 `watchlist_match` 브로드캐스트.
4. 프론트 notifications 패널에 🔖 배지 + "워치리스트 매칭: {키워드} → {기사 제목}" 표시. 클릭 시 뉴스 상세 이동.

**매칭 로직** (scheduler.py `collection_pipeline` 내부, `classify_batch` 결과 처리 후):
```python
# 활성 워치리스트 로드
active = (await db.execute(
    select(Watchlist).where(Watchlist.is_active == True)
)).scalars().all()

for analysis in analyses:  # 이번 배치 분류 결과
    for w in active:
        if _matches(w.keyword, analysis):
            broadcast_event("watchlist_match", {
                "keyword": w.keyword,
                "article_id": str(analysis.article_id),
                "article_title": analysis.article.title,
            })
            w.match_count += 1
            w.last_matched_at = datetime.now(timezone.utc)
await db.commit()
```
`_matches(keyword, analysis)`:
- `keyword in (analysis.keywords or [])` (정확 매칭)
- OR `agenda._title_contains(analysis.article.title, keyword)` (기존 경계 매칭 재사용 — 한글 3자↑ / 영숫자 단어경계)

**UX**:
- `/watchlist` 페이지: 키워드 추가 input + 활성화 토글 + 매칭 횟수·최근 매칭 시각 표시.
- 대시보드 상단 퀵 추가 input 선택 (간단 MVP는 /watchlist 페이지 단일).
- notifications.tsx에 이벤트 config 추가: `watchlist_match: { icon: Bookmark, label: "워치리스트 매칭" }`.

**저장**: DB 테이블 `watchlists`. `Base.metadata.create_all` 이 서버 재기동 시 자동 생성 (기존 데이터는 보존).

---

## 2. API 추가 명세

### 2-1. POST /api/v1/drafts/generate
```json
// Request
{
  "article_ids": ["uuid1", "uuid2"],   // 1개 이상
  "style": "straight",                  // 선택: straight|analysis|feature
  "topic_hint": "호르무즈 해협 개방"    // 선택: 진입점 컨텍스트
}

// Response.data
{
  "title_candidates": ["제목1", "제목2", "제목3"],
  "lead": "리드 문단 (2~3문장)",
  "body": "본문 Markdown 텍스트",
  "background": "맥락/배경 (~300자)",
  "six_w_check": {
    "who": "...",
    "when": "...",
    "where": "...",
    "what": "...",
    "how": "...",
    "why": null
  },
  "sources": [
    {"name": "연합뉴스", "url": "https://..."},
    {"name": "BBC", "url": "https://..."}
  ],
  "model_used": "claude-sonnet-4-6",
  "prompt_tokens": 1234,
  "completion_tokens": 567,
  "generated_at": "2026-04-19T12:00:00Z"
}
```
- 에러:
  - 400 — article_ids 빈 배열
  - 404 — 기사 중 존재하지 않는 id
  - 500 — LLM 스키마 검증 실패

### 2-2. 워치리스트 CRUD
```
GET    /api/v1/watchlist
  → data: [{id, keyword, is_active, created_at, last_matched_at, match_count}]

POST   /api/v1/watchlist
  body: {keyword: "호르무즈"}
  → data: {id, keyword, is_active: true, created_at, match_count: 0}

PATCH  /api/v1/watchlist/{id}
  body: {is_active: false}
  → data: 업데이트된 항목

DELETE /api/v1/watchlist/{id}
  → data: {deleted: true}
```
- 에러: 409 (keyword 중복), 404 (id 없음), 422 (keyword 빈 문자열).

### 2-3. SSE 이벤트 추가
```
event: watchlist_match
data: {"keyword": "호르무즈", "article_id": "...", "article_title": "..."}
```

---

## 3. DB 변경

### watchlists 테이블 (신규)
```python
class Watchlist(Base):
    __tablename__ = "watchlists"

    id: uuid.UUID (PK, default=uuid4)
    keyword: str(100) (UNIQUE, index)
    is_active: bool (default=True)
    created_at: datetime (server_default=now())
    last_matched_at: datetime | None
    match_count: int (default=0)
```
- 생성: `backend/main.py` 의 lifespan에서 `init_db()` → `Base.metadata.create_all` 이 처리. 기존 테이블 영향 없음.
- 인덱스: `keyword` 에 unique 제약으로 자동 인덱스. `is_active` 필터링 빈도 높아 보조 인덱스 고려 (선택).

### 다른 테이블 수정 없음
초안(`drafts`)은 요청마다 즉시 응답 — 저장하지 않음 (MVP). 저장 필요 시 추후 `drafts` 테이블 추가.

---

## 4. 프론트 구현 포인트

### 재사용
- `frontend/src/lib/api.ts` — `fetchAPI<T>` 래퍼에 `generateDraft`, `getWatchlist`, `addWatchlist`, `deleteWatchlist`, `patchWatchlist` 함수 추가.
- `frontend/src/components/notifications.tsx` — `eventConfig` 에 `watchlist_match` 항목 추가 + `handleEvent` 에 메시지 포맷.
- `frontend/src/components/sidebar.tsx` — `navItems` 에 `{ href: "/watchlist", label: "워치리스트", icon: Bookmark }` 추가.
- lucide-react 아이콘: `Copy`, `Mail`, `FileEdit`, `Bookmark` (이미 설치).

### 신규 파일
| 경로 | 역할 |
|------|------|
| `frontend/src/lib/clipboard.ts` | `copyToClipboard(text): Promise<boolean>` + 공용 훅 |
| `frontend/src/components/copy-button.tsx` | `<CopyButton value size? />` 4곳 진입점 공유 |
| `frontend/src/components/draft-dialog.tsx` | 초안 생성 요청/결과 모달 (진입 3곳 공유) |
| `frontend/src/components/ui/dialog.tsx` | shadcn `dialog` 컴포넌트 (CLI 설치) |
| `frontend/src/app/watchlist/page.tsx` | 워치리스트 CRUD 페이지 |

### 기존 파일 수정
| 경로 | 변경 |
|------|------|
| `frontend/src/app/news/[id]/page.tsx` | 헤더에 CopyButton + "초안 작성" 버튼 → DraftDialog 트리거 |
| `frontend/src/app/reports/page.tsx` | "마크다운 복사" + "메일로 보내기" + 섹션별 CopyButton |
| `frontend/src/app/headlines/page.tsx` | 추천 헤드라인 각각에 CopyButton + "이 제목으로 초안" |
| `frontend/src/app/analysis/page.tsx` | 의제 카드에 CopyButton + "이 이슈로 초안" |
| `frontend/src/app/page.tsx` (대시보드) | 의제 Top 5 섹션에 동일 버튼 |
| `frontend/src/components/sidebar.tsx` | 네비에 `/watchlist` |
| `frontend/src/components/notifications.tsx` | `watchlist_match` 이벤트 처리 |

### shadcn Dialog 설치 필요
현재 `frontend/src/components/ui/` 에 `dialog.tsx` 없음. 다음 명령 필요:
```bash
cd frontend && npx shadcn@latest add dialog
```

### Next.js 16 주의
`frontend/AGENTS.md` 고지: **이 프로젝트의 Next.js 는 학습 데이터와 다르다. 코드 작성 전 `node_modules/next/dist/docs/` 관련 가이드 확인 필수.** 서버/클라이언트 컴포넌트 경계, `useRouter`, 폼 액션 등 breaking change 가능성 대비.

---

## 5. 수동 QA 체크리스트 (7 시나리오)

| # | 시나리오 | 기대 결과 |
|---|---------|----------|
| 1 | 뉴스 상세 "복사" 클릭 후 메모장 붙여넣기 | 제목·매체·발행일·요약·URL 4줄 포맷 정확 |
| 2 | 브리핑 "마크다운 전체 복사" → 마크다운 뷰어 | 헤더·섹션 구조 정상 렌더, 한글 깨짐 없음 |
| 3 | 브리핑 "메일로 보내기" 클릭 | 기본 메일 앱 열림, subject/body 채워짐 |
| 4 | 의제 카드에서 "이 이슈로 초안" → 모달 | 제목 3안 + 리드 + 본문 + 6하원칙 표시 |
| 5 | 초안 응답 JSON을 Pydantic 검증 | DraftOut 통과, 누락 필드 없음 |
| 6 | 워치리스트 "호르무즈" 등록 → 다음 수집 사이클 | 매칭 시 notifications 에 🔖 알림 출현 |
| 7 | 워치리스트 항목 비활성 토글 | 이후 사이클에서 해당 키워드 알림 끊김 |

---

## 6. 알려진 한계

- **PDF 미지원**: 사용자 결정. 필요 시 추후 react-pdf 도입.
- **단일 사용자 가정**: 개인화·권한·멀티테넌트 없음 (과제 스코프 외).
- **초안 저장 안 함**: 모달 닫으면 사라짐. 기자가 복사하지 않으면 재생성 필요.
- **Article.content 결측 영향**: RSS/Naver 기사는 `content` 대부분 없어 초안이 `title + description` 에 의존. Sonnet 4.6 프롬프트에 "원문에 없는 사실 추측 금지" 명시로 완화.
- **워치리스트 부분 매칭 한계**: `_title_contains` 규칙 기반이라 동의어/오탈자 매칭 불가. 추후 임베딩 기반으로 확장 여지.
- **비용**: Sonnet 초안 1건당 ~$0.05. 대량 호출 방지 필요 시 rate limit 고려.

---

## 7. 구현 순서 (코딩 턴에서)

1. **백엔드 모델/스키마**
   - `backend/database/models.py` Watchlist 추가
   - `backend/analyzers/schemas.py` DraftOut, SixWCheckOut, WatchlistOut 추가
2. **프롬프트 + 라우터**
   - `backend/prompts.py` DRAFT_SYSTEM 추가
   - `backend/analyzers/llm_client.py` `MODEL_FOR["draft"] = SONNET_MODEL`
   - `backend/routers/drafts.py` 신규
   - `backend/routers/watchlist.py` 신규
   - `backend/main.py` include_router 2개 추가
3. **스케줄러 훅**
   - `backend/scheduler.py` 워치리스트 매칭 블록 추가
4. **프론트 기반**
   - `npx shadcn@latest add dialog`
   - `frontend/src/lib/clipboard.ts`
   - `frontend/src/lib/api.ts` 함수 5개 추가
   - `frontend/src/components/copy-button.tsx`
   - `frontend/src/components/draft-dialog.tsx`
5. **프론트 진입점 삽입**
   - 뉴스 상세 / 브리핑 / 헤드라인 / 분석 / 대시보드 각 페이지 수정
   - sidebar / notifications 수정
6. **워치리스트 페이지**
   - `frontend/src/app/watchlist/page.tsx`
7. **테스트**
   - `backend/tests/test_unit.py` DraftOut 검증, 워치리스트 매칭 함수 유닛 테스트
   - `backend/tests/test_api.py` 신규 엔드포인트 API 테스트
8. **수동 QA** (§5 7시나리오)
