# 배포 가이드 — Supabase + Fly.io + Vercel

무료 티어로 뉴스룸 AI 프로토타입을 전부 띄우는 레시피. 로컬 `docker compose` 재현성이 이미 잡혀 있고, 그 구성요소를 각 무료 호스팅에 1:1 로 옮기는 과정이다.

구성:
- **Postgres** → Supabase (500MB free, always-on, JSONB 지원)
- **Backend (FastAPI + APScheduler + SSE)** → Fly.io (small shared VM, always-on — 스케줄러 필요)
- **Frontend (Next.js)** → Vercel (Hobby)

Fly 는 가입 시 결제 수단 등록이 필요하지만 작은 VM 하나는 무료 할당 안에서 요금 청구 없음 (2025년 이후 정책 기준; 실제 청구 여부는 본인 대시보드에서 확인).

---

## 0. 사전 준비

```bash
# flyctl (Fly CLI) 설치 — Windows PowerShell
iwr https://fly.io/install.ps1 -useb | iex

# 또는 macOS/Linux
curl -L https://fly.io/install.sh | sh

fly version    # 설치 확인
fly auth login # 브라우저 로그인(없으면 signup)
```

Anthropic API 키(`sk-ant-...`) 는 미리 준비.

---

## 1. Supabase Postgres 생성

1. <https://supabase.com> 가입 → **New Project**
2. 프로젝트명 `newsroom-ai`, Region `Northeast Asia (Seoul)` 또는 `Tokyo`, DB 비밀번호 임의 설정 (저장 필수)
3. 프로젝트 만들어지면 → **Project Settings** → **Database** → **Connection string** 탭
4. **Session pooler** 의 URI 를 복사:
   ```
   postgresql://postgres.[project-ref]:[PASSWORD]@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres
   ```
5. 이걸 SQLAlchemy + asyncpg 용으로 변환:
   ```
   postgresql+asyncpg://postgres.[project-ref]:[PASSWORD]@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres
   ```
   `postgresql://` → `postgresql+asyncpg://` 로 바꾸는 게 유일한 변경점.

> ⚠️ Transaction pooler(포트 6543) 는 asyncpg 의 prepared statement 캐시와 충돌. 반드시 Session pooler(5432) 또는 Direct connection 사용.

---

## 2. Fly 에 백엔드 배포

저장소 루트에서:

```bash
# 앱 등록 (fly.toml 의 app 이름이 이미 점유 중이면 다른 이름 프롬프트가 뜸)
fly launch --copy-config --no-deploy

# 시크릿 주입
fly secrets set \
  ANTHROPIC_API_KEY='sk-ant-xxxxx' \
  DATABASE_URL='postgresql+asyncpg://postgres.[ref]:[pw]@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres' \
  CORS_ORIGINS='["http://localhost:3000"]'

# 배포
fly deploy
```

배포 끝나면 `https://<app-이름>.fly.dev/api/v1/health` 가 200 을 반환해야 정상.

```bash
curl https://<app>.fly.dev/api/v1/health
```

로그는:
```bash
fly logs
```

---

## 3. Vercel 에 프론트엔드 배포

GitHub 에 푸시 후:

1. <https://vercel.com/new> → 저장소 임포트
2. **Root Directory**: `frontend` 로 설정 (중요 — 그렇지 않으면 Next.js 감지 실패)
3. **Environment Variables** 추가:
   ```
   NEXT_PUBLIC_API_URL = https://<fly-app>.fly.dev/api/v1
   ```
4. **Deploy** 클릭

배포 URL(`https://newsroom-ai.vercel.app` 형태) 확인.

---

## 4. CORS 갱신

Vercel 도메인이 나왔으니 Fly 쪽 CORS 허용 목록에 추가:

```bash
fly secrets set CORS_ORIGINS='["https://newsroom-ai.vercel.app","http://localhost:3000"]'
# 시크릿 변경 시 자동 재배포됨
```

---

## 5. 첫 수집 트리거

스케줄러가 15분 주기로 도는데 즉시 결과 보고 싶으면:

```bash
curl -X POST https://<fly-app>.fly.dev/api/v1/collect
```

Vercel URL 열어서 대시보드·의제·편집실 흐름 확인.

---

## 트러블슈팅

### `fly deploy` 시 health check 실패
- Fly 로그 확인: `fly logs`
- 대개 `DATABASE_URL` 잘못 / Supabase 비번 오타 / `postgresql+asyncpg://` 접두어 누락
- Fly 시크릿 재설정: `fly secrets list` 로 키 존재 확인, 문제 있으면 `fly secrets unset KEY` 후 재설정

### asyncpg `prepared statement does not exist`
- Transaction pooler(6543) 사용 중이라는 뜻. Session pooler(5432) 로 교체.

### Vercel 빌드에서 `NEXT_PUBLIC_API_URL` 이 localhost 로 박힘
- Env var 추가 후 **Redeploy** 를 눌러야 재빌드됨. 기존 빌드 캐시는 localhost 로 고정.

### Fly VM 자원 부족 / OOM
- `fly.toml` 의 `memory_mb` 를 1024 로 늘리고 `fly deploy`. 무료 할당을 초과할 수 있으니 대시보드 확인.

### 스케줄러가 두 번 돈다
- `fly scale count 1` 로 인스턴스 수를 1개로 고정 (fly.toml 의 `min_machines_running=1` 이 통상 이 역할이지만, 스케일 아웃한 이력이 있으면 명시적으로 줄여야 함).

---

## 제거

```bash
fly apps destroy <app-이름>
# Supabase, Vercel 은 대시보드에서 프로젝트 삭제
```
