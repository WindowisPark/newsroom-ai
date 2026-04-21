# Newsroom AI

공개 API·RSS 로 국내외 뉴스를 실시간 수집·분석하고, 의제 추출 → 브리핑 생성 → 기사 초안 작성 → 편집실 결재 워크플로까지 자동화하는 AI 뉴스룸 프로토타입. (서울신문 AI 서비스 개발자 채용 실무평가 과제)

## 배포된 주소

- 프론트: <https://newsroom-ai-jet.vercel.app>
- 백엔드: <https://newsroom-ai-backend.fly.dev>
- API 문서(Swagger): <https://newsroom-ai-backend.fly.dev/docs>

## 로컬 실행

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

처음 부팅에는 3~5분 정도 걸리고, 백엔드가 뜨는 순간 15분 간격의 수집 스케줄러와 `BRIEFING_SCHEDULE`(기본 `09:00,18:00`) 시각의 브리핑/의제 cron 잡이 자동으로 돌기 시작합니다. 직후 첫 수집을 트리거하려면:

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
- `/analysis` — 국내 vs 외신 관점 비교 리포트
- `/reports` — 일일 브리핑 + 의제별 초안 작성 다이얼로그
- `/headlines` — 기사 작성 보조(헤드라인 3선 + 배경 타임라인)
- `/newsroom` — 예비 기사(AI 초안) → 편집 → 결재 → 승인·게시 워크플로
- `/watchlist` — 워치리스트(키워드) 관리
- `/system` — 수집·분석 스케줄러 상태 및 수동 트리거

## 아키텍처 개요

```
┌──────────────┐        ┌──────────────────────────────────────┐
│  Next.js 16  │ ◀───── │              FastAPI                │
│  (React 19)  │  REST  │  ┌───────────────────────────────┐  │
│              │  + SSE │  │ collectors  (RSS/NewsAPI/네이버) │  │
└──────────────┘        │  └───────────────────────────────┘  │
                        │  ┌───────────────────────────────┐  │
                        │  │ analyzers                      │  │
                        │  │  classifier  (Haiku 4.5)       │  │
                        │  │  agenda      (Sonnet 4.6)      │  │
                        │  │  perspective (Sonnet 4.6)      │  │
                        │  │  reporter    (Sonnet 4.6)      │  │
                        │  │  headline    (Sonnet 4.6)      │  │
                        │  │  drafter     (Sonnet 4.6 + RAG)│  │
                        │  │  fact_check  (규칙기반 L2)      │  │
                        │  │  reviewer    (Gemini 3 Flash)  │  │
                        │  └───────────────────────────────┘  │
                        │  ┌───────────────────────────────┐  │
                        │  │ APScheduler                    │  │
                        │  │   · 15분 interval — 수집+분류   │  │
                        │  │   · cron (09:00/18:00) — 브리핑 │  │
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

과제 허용 모델 중 3종 조합. 단계별 복잡도와 "생성 ≠ 판독" 분리 원칙에 따라 배치.

- **Claude Haiku 4.5** — 기사 1차 분류(카테고리·키워드·감성·중요도), 외신 검색용 Korean→English 키워드 번역. 대량·단순·구조화 JSON 작업.
- **Claude Sonnet 4.6** — 의제 도출, 관점 비교, 타임라인, 기사 초안 생성. 다중 문서 교차 추론·작문.
- **Google Gemini 3 Flash** — 기사 초안 **품질 판독**(이종 judge). 생성 모델과 학습 계보가 다른 모델로 self-critique 편향을 피함.

프론트엔드는 어떤 LLM 도 직접 호출하지 않고 모두 백엔드 경유 (`backend/analyzers/llm_client.py` 는 Anthropic, `backend/analyzers/gemini_client.py` 는 Google GenAI 의 단일 진입점).

## 분석 파이프라인

LLM 단독이 아니라 **통계 집계 → LLM 판단 → 규칙 후처리** 하이브리드 구조. 집계·검증은 결정론적 코드로, 의미 판단만 LLM 이 맡는다.

| 단계 | 모듈 | 모델 | 알고리즘 |
|---|---|---|---|
| L1 분류 | `classifier.py` | Haiku 4.5 | 기사 1건당 JSON 스키마(Pydantic) 강제 호출 → 카테고리/키워드/엔티티/감성/importance(0~10). 본문 1000자 초과 시 머리 60% + 꼬리 40% 절단, 3회 실패 시 blocklist |
| L1.5 부스팅 | `classifier.py` | — | 하루 DB 전체에서 키워드별 **고유 매체 수** 집계 → 2곳 +0.7, 3곳 +1.4, 4+곳 +2.0 importance 가산. "주요 이슈 = 여러 매체가 교차 보도한 사안" 편집국 관행 반영 |
| L2 의제설정 | `agenda.py` | Sonnet 4.6 | 2단계 하이브리드: ① `Counter`/`defaultdict(set)` 로 키워드 빈도·매체 수·카테고리·감성·평균 중요도 사전 집계 ② 집계 텍스트 + 상위 50건 요약을 LLM 에 주고 Top-N 의제 생성. 후처리는 키워드 교집합 매칭 + 한글 3자 이상 단어경계 정규식 fallback |
| L2b 관점비교 | `perspective.py` | Sonnet 4.6 (+ Haiku 번역) | `source_type = domestic` vs `foreign` 분리 조회 후 교차 제시. 외신 RSS 제목이 영문이라 한국어 topic ILIKE 로는 0건 매칭 → Haiku 로 한국어 topic → English 키워드 3~5개 변환(예: "호르무즈 해협" → "Strait of Hormuz") 후 외신 쪽에만 적용 |
| L3 팩트검증 | `fact_check.py` | 규칙기반 | 3 검증기: ① entity KB 직책 불일치(high) ② 수치 grounding — 정규식 추출 후 원문에 없으면 경고(medium, "1만↔10000" 단위변환 허용) ③ KB 미등재 인물 grounding(low). high 경고는 HITL ack 필수 |
| L4 생성 | `reporter.py`, `headline.py`, `drafter.py` | Sonnet 4.6 (+RAG) | 일일 브리핑 / 헤드라인 3선 + 타임라인 / 기사 초안. drafter 는 매체를 own·agency·competitor·other 4-tier 로 나눠 인용 정책 차등화, 서울신문 자사 기사 최근 90일 retrieval 해 톤 앵커로 주입. **입력단 가드**: agency 비율 ≥70% + own 0건이면 wire-redistribution 위험으로 400 차단 |
| L4' 품질 판독 | `reviewer.py` | **Gemini 3 Flash** (이종 judge) | drafter 직후 자동 호출. 7축 0–10점(리드 강도·6하원칙·역피라미드·톤·인용정책·사실 구체성·**자사 독자성**) + publish/revise/reject 추천 + 수정 제안. Structured Output + Pydantic 이중 검증. 판독 실패해도 초안 생성은 유지(graceful). 모든 결과는 `ArticleDraft.quality_review` JSONB 에 스냅샷 저장 |

핵심 의사결정:
- **3-provider 차등 배치** — Haiku(분류·번역) → Sonnet(의제·생성) → Gemini(판독). 복잡도 기반 비용 최적화 + **생성과 판독을 서로 다른 회사 모델로 분리**하여 자가평가 편향 제거.
- **집계는 SQL·Python 으로 선행** 해 LLM 토큰 절약 (의제의 키워드·매체수 사전 집계, drafter 의 JSONB `has_any` 후보 축소).
- **검증·부스팅은 LLM 이 아닌 결정론적 규칙** 으로 재현 가능성 확보 (팩트 검증 3종, 매체수 가산, entity KB, source diversity guard).
- **편집국 관행 반영** — 매체 4-tier 인용 정책, 교차 보도 중요도 보정, 통신사 의존도 감점, 팩트 HITL ack.

### 신뢰성 · 관측성

- **LLM 재시도** — Anthropic `call_llm` / Gemini `call_gemini` 모두 `tenacity` 지수 백오프 3회 (1s → 2s → 4s, 최대 10s). 연결/타임아웃/429/5xx 만 재시도하고, 4xx(스키마·인증 오류)는 즉시 실패 전파.
- **비용 추적** — `ArticleAnalysis.prompt_tokens`/`completion_tokens` 컬럼에 분류기 Haiku 호출 토큰 누적 저장. `AgendaReport`·`BriefingReport`·`ArticleDraft.quality_review` 의 토큰 필드와 합쳐 모델별 일 단위 비용 집계 가능.
- **실시간 RAG 성능** — `drafter._retrieve_by_tier` 는 티어(source_name)·recency·키워드(JSONB `has_any`)를 SQL 레벨에서 필터링해 후보를 200건 이하로 축소한 뒤 Python 에서 재랭킹. `keywords` 컬럼에 GIN 인덱스(`ix_article_analyses_keywords_gin`) 를 걸어 수만 건 규모에서도 LLM 호출 대비 retrieval 지연 무시 가능.
- **자동 보고 cron** — `BRIEFING_SCHEDULE="09:00,18:00"` 처럼 일 다회성 스케줄 지원. 수집 파이프라인과 독립 실행되며, `auto_report_min_articles` 미만이면 건너뛴다.
- **이종 판독 graceful degradation** — Gemini 실패 시(키 미설정·quota·네트워크) 초안 생성은 그대로 성공하고 `quality_review: null` 로 반환. 판독 층이 끊겨도 핵심 플로우(수집→분류→의제→초안→HITL) 는 유지.
- **JSON 파싱 견고성** — Sonnet 이 body Markdown 에 raw 개행을 섞는 경우를 대비해 `json.loads(..., strict=False)` 허용 + 파싱 실패 시 `stop_reason`/`head`/`tail` 상세 로깅.

## 확장 경로

현재 구조는 하루 수백~수천 건 규모의 프로토타입에 맞춰져 있다. 프로덕션 전환 시 예상 리팩토링 지점:

- **수집/분석 큐 분리** — 현 APScheduler 단일 프로세스 직렬 실행은 대선·재난 등 기사 폭증 상황에서 15분 사이클 내 완료를 보장하지 못한다. Redis + ARQ/Celery 로 수집 producer ↔ 분석 worker 를 분리하면 분석 워커를 수평 확장할 수 있다.
- **멀티워커 blocklist 공유** — `classify_batch` 의 실패 차단 세트가 인-메모리라 uvicorn `--workers > 1` 환경에서 프로세스 간 공유되지 않는다. Redis 해시 또는 DB 컬럼(`Article.classify_failures`) 으로 옮기면 해결.
- **entity_kb 자동 갱신** — 현재는 수동 YAML. 공공데이터포털 공직자 DB 또는 Wikidata 로 일 단위 동기화 스크립트를 추가하면 `role_mismatch` coverage 가 현재 4건 → 수백 건으로 확장된다.
- **외부 채널 연동** — 현 "자동 보고" 채널은 자체 대시보드 + SSE. 필요 시 `scheduled_reports_job` 말단에 Slack webhook · 이메일 발송 훅을 10~15줄로 추가.
- **스키마 마이그레이션** — 현재 `Base.metadata.create_all` 로 기동 시 자동 생성. 프로토타입 단계에서 컬럼 추가 시 `docker compose down -v` 로 DB 를 초기화하거나, `create_all` 은 기존 테이블에는 손대지 않으므로 컬럼 추가분만 psql 로 수동 `ALTER TABLE` 해주면 된다. 실제 배포 시에는 alembic 도입 권장.

## AI 도구 사용 내역

과제 요건에 따른 고지.

### 런타임 LLM (프로덕트 기능)
- **Claude Haiku 4.5** (Anthropic) — 1차 분류, 외신 검색용 Korean→English 키워드 번역
- **Claude Sonnet 4.6** (Anthropic) — 의제 도출, 관점 비교, 타임라인, 기사 초안 생성
- **Gemini 3 Flash** (Google) — 초안 품질 판독(이종 judge, 7축 editorial 평가)

### 개발 도구
- **Claude Code**(Claude Opus 4.7, 1M context) — 이 저장소의 설계 논의·구현·리팩토링 전반에 사용. 개발 플로우는 대략:
  1. 요구사항/과제 조건 분석 → 인용 정책·RAG·이종 judge 설계 초안을 대화로 결정
  2. 모듈 단위로 구현 요청 후 생성 결과를 읽고 수정·통합
  3. `/simplify` 로 주기적 코드 리뷰 + 공통 모듈 추출, 리뷰 지적 사항을 사람이 판단해 수용/기각
  4. 테스트(backend/tests) 를 함께 작성하고 `pytest`/`tsc --noEmit` 로 검증
- **shadcn/ui**(CLI) — 기본 컴포넌트(Card/Button/Tabs/Dialog 등) scaffold
- **Tailwind v4** — 스타일링

주요 설계 결정(자사 RAG 4-tier 인용 정책, 팩트검증 3 검증기, HITL ack 워크플로, 이종 judge 7축 판독, wire-redistribution 입력 가드) 은 모두 개발자가 판단·검토했으며, LLM 이 제안한 코드도 전부 실제로 빌드·실행해 확인했습니다.

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
