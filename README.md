# Newsroom AI

공개 API·RSS 로 국내외 뉴스를 실시간 수집·분석하고, 의제 추출 → 브리핑 생성 → 기사 초안 작성 → 편집실 결재 워크플로까지 자동화하는 AI 뉴스룸 프로토타입. (서울신문 AI 서비스 개발자 채용 실무평가 과제)

## 빠른 실행

요구: Docker Desktop, Anthropic API 키.

```bash
cp .env.example .env
# .env 파일을 열어 ANTHROPIC_API_KEY 한 줄만 채우면 됩니다.

docker compose up --build
```

- 프론트: <http://localhost:3000>
- 백엔드: <http://localhost:8000>
- API 문서(Swagger): <http://localhost:8000/docs>
- Postgres: `localhost:5432` (user: `postgres`, pw: `postgres`, db: `newsroom`)

처음 부팅에는 3~5분 정도 걸리고, 백엔드가 뜨는 순간 15분 간격의 RSS 수집 스케줄러가 자동으로 돌기 시작합니다. 직후 첫 수집을 트리거하려면:

```bash
curl -X POST http://localhost:8000/api/v1/collect
```

### Supabase 등 외부 Postgres 를 쓰고 싶다면

`.env` 에 `DATABASE_URL` 을 지정하고 compose 의 `postgres` 서비스는 무시됩니다:

```
DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[pw]@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres
```

## 주요 화면

- `/` — 실시간 대시보드(최신 뉴스 + 오늘의 의제)
- `/news` — 기사 목록 · 카테고리/감성 필터
- `/reports` — 일일 브리핑 + 의제별 초안 작성 다이얼로그
- `/newsroom` — 예비 기사(AI 초안) → 편집 → 결재 → 승인·게시 워크플로
- `/watchlist` — 워치리스트(키워드) 관리

## 아키텍처 개요

```
┌──────────────┐        ┌──────────────────────────────────────┐
│  Next.js 16  │ ◀───── │              FastAPI                │
│  (React 19)  │  REST  │  ┌───────────────────────────────┐  │
│              │  + SSE │  │ collectors  (RSS/NewsAPI/네이버) │  │
└──────────────┘        │  └───────────────────────────────┘  │
                        │  ┌───────────────────────────────┐  │
                        │  │ analyzers                      │  │
                        │  │  classifier (Haiku 4.5)        │  │
                        │  │  agenda     (Sonnet 4.6)       │  │
                        │  │  drafter    (Sonnet 4.6 + RAG) │  │
                        │  │  fact_check (규칙기반 L2)       │  │
                        │  └───────────────────────────────┘  │
                        │  ┌───────────────────────────────┐  │
                        │  │ APScheduler: 15분 주기 수집    │  │
                        │  └───────────────────────────────┘  │
                        └──────────────────┬───────────────────┘
                                           │
                                    ┌──────▼───────┐
                                    │  PostgreSQL  │
                                    │  (JSONB)     │
                                    └──────────────┘
```

설계 근거와 인용 정책 등 자세한 내용은 [`docs/REFERENCES.md`](docs/REFERENCES.md), [`docs/API_SPEC.md`](docs/API_SPEC.md), [`docs/UX_FEATURES.md`](docs/UX_FEATURES.md) 참조.

## LLM 모델

- **Haiku 4.5** — 기사 1차 분류(카테고리·감성·중요도)
- **Sonnet 4.6** — 의제 추출, 일일 브리핑, 기사 초안 생성

프론트엔드는 LLM 을 직접 호출하지 않고 모두 백엔드 경유 (`backend/analyzers/llm_client.py` 단일 진입점).

## AI 도구 사용 내역

과제 요건에 따른 고지.

- **Claude Code**(Claude Opus 4.7, 1M context) — 이 저장소의 설계 논의·구현·리팩토링 전반에 사용. 개발 플로우는 대략:
  1. 요구사항/과제 조건 분석 → 인용 정책·RAG 설계 초안을 대화로 결정
  2. 모듈 단위로 구현 요청 후 생성 결과를 읽고 수정·통합
  3. `/simplify` 로 주기적 코드 리뷰 + 공통 모듈 추출, 리뷰 지적 사항을 사람이 판단해 수용/기각
  4. 테스트(backend/tests) 를 함께 작성하고 `pytest`/`tsc --noEmit` 로 검증
- **shadcn/ui**(CLI) — 기본 컴포넌트(Card/Button/Tabs/Dialog 등) scaffold.
- **Tailwind v4** — 스타일링.

주요 설계 결정(자사 RAG 3 계층 인용 정책, 팩트검증 3 검증기, HITL ack 워크플로) 은 모두 개발자가 판단·검토했으며, LLM 이 제안한 코드도 전부 실제로 빌드·실행해 확인했습니다.

## 배포

무료 티어로 올리는 레시피(Supabase + Fly.io + Vercel) 는 [`docs/DEPLOY.md`](docs/DEPLOY.md) 참조. 루트의 `fly.toml` 이 백엔드 배포 설정을 담고 있음.

## 개발 환경(Docker 없이)

```bash
# Backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
# Postgres 가 로컬에 있어야 함. .env 에 DATABASE_URL 설정.
uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## 테스트

```bash
# 백엔드 유닛(빠름, DB 불필요)
pytest backend/tests/test_unit.py -v

# 전체(Postgres 필요)
pytest backend/tests/ -v
```

## 라이선스

과제 제출용 프로토타입.
