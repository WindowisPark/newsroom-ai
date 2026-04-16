# Newsroom AI - API 명세서

> 모든 API는 `http://localhost:8000/api/v1` 기준입니다.
> 날짜 형식: ISO 8601 (`2026-04-16T09:00:00Z`)

---

## 공통 응답 형식

### 성공
```json
{
  "status": "success",
  "data": { ... },
  "meta": { "total": 100, "page": 1, "limit": 20 }
}
```

### 에러
```json
{
  "status": "error",
  "message": "설명",
  "code": "ERROR_CODE"
}
```

---

## 1. 뉴스 (News)

### 1-1. 뉴스 목록 조회
```
GET /news
```

**Query Parameters:**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| page | int | N | 1 | 페이지 번호 |
| limit | int | N | 20 | 페이지당 개수 (max 100) |
| category | string | N | - | 카테고리 필터 (politics, economy, society, world, tech, culture, sports) |
| sentiment | string | N | - | 감성 필터 (positive, negative, neutral) |
| source_type | string | N | - | 소스 타입 (domestic, foreign) |
| sort_by | string | N | importance | 정렬 기준 (importance, published_at, created_at) |
| q | string | N | - | 키워드 검색 |

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "title": "기사 제목",
      "description": "기사 요약",
      "content": "기사 본문 (있을 경우)",
      "url": "https://...",
      "source_name": "연합뉴스",
      "source_type": "domestic",
      "published_at": "2026-04-16T09:00:00Z",
      "collected_at": "2026-04-16T09:05:00Z",
      "analysis": {
        "category": "politics",
        "keywords": ["키워드1", "키워드2"],
        "entities": [
          { "name": "홍길동", "type": "person" },
          { "name": "외교부", "type": "organization" }
        ],
        "sentiment": "neutral",
        "importance_score": 8.5
      }
    }
  ],
  "meta": { "total": 253, "page": 1, "limit": 20 }
}
```

### 1-2. 뉴스 상세 조회
```
GET /news/{news_id}
```

**Response:** 단일 뉴스 객체 (1-1과 동일 구조)

### 1-3. 수동 수집 트리거
```
POST /news/collect
```

**Request Body:**
```json
{
  "sources": ["newsapi", "naver", "rss"],
  "query": "선택적 검색 키워드"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "collected_count": 45,
    "new_count": 38,
    "duplicate_count": 7,
    "sources": {
      "newsapi": 15,
      "naver": 18,
      "rss": 12
    }
  }
}
```

---

## 2. 분석 (Analysis)

### 2-1. 의제 설정 분석 (Agenda Setting)
```
GET /analysis/agenda
```

**Query Parameters:**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| date | string | N | today | 분석 대상 날짜 (YYYY-MM-DD) |
| top_n | int | N | 5 | 상위 N개 이슈 |

**Response:**
```json
{
  "status": "success",
  "data": {
    "date": "2026-04-16",
    "generated_at": "2026-04-16T10:30:00Z",
    "top_issues": [
      {
        "rank": 1,
        "topic": "이슈 주제",
        "summary": "이 이슈에 대한 2~3줄 요약",
        "importance_score": 9.2,
        "article_count": 28,
        "source_count": 12,
        "trend": "rising",
        "categories": ["politics", "economy"],
        "key_keywords": ["키워드1", "키워드2", "키워드3"],
        "related_article_ids": ["uuid1", "uuid2"]
      }
    ],
    "analysis_summary": "오늘 뉴스룸이 주목해야 할 핵심 의제에 대한 종합 분석..."
  }
}
```

### 2-2. 관점 비교 (Perspective Comparison)
```
GET /analysis/perspective
```

**Query Parameters:**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| topic | string | Y | - | 비교할 이슈 주제 또는 키워드 |
| date | string | N | today | 대상 날짜 |

**Response:**
```json
{
  "status": "success",
  "data": {
    "topic": "요청한 주제",
    "generated_at": "2026-04-16T10:35:00Z",
    "domestic": {
      "frame": "국내 매체의 보도 프레임 요약",
      "tone": "neutral",
      "key_points": ["포인트1", "포인트2"],
      "representative_articles": [
        {
          "id": "uuid",
          "title": "기사 제목",
          "source_name": "서울신문",
          "url": "https://..."
        }
      ]
    },
    "foreign": {
      "frame": "외신의 보도 프레임 요약",
      "tone": "critical",
      "key_points": ["포인트1", "포인트2"],
      "representative_articles": [
        {
          "id": "uuid",
          "title": "Article Title",
          "source_name": "Reuters",
          "url": "https://..."
        }
      ]
    },
    "comparison": {
      "frame_difference": "프레임 차이에 대한 분석",
      "background_context": "차이가 발생하는 정치적/문화적 맥락 설명",
      "editorial_insight": "편집 관점에서의 시사점"
    }
  }
}
```

### 2-3. 트렌드 분석
```
GET /analysis/trends
```

**Query Parameters:**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| period | string | N | 24h | 기간 (6h, 12h, 24h, 7d) |
| type | string | N | keyword | 트렌드 타입 (keyword, category, sentiment) |

**Response:**
```json
{
  "status": "success",
  "data": {
    "period": "24h",
    "type": "keyword",
    "data_points": [
      {
        "label": "키워드명",
        "values": [
          { "time": "2026-04-16T00:00:00Z", "count": 5 },
          { "time": "2026-04-16T06:00:00Z", "count": 12 },
          { "time": "2026-04-16T12:00:00Z", "count": 8 }
        ]
      }
    ]
  }
}
```

---

## 3. 리포트 (Reports)

### 3-1. 브리핑 리포트 조회
```
GET /reports/briefing
```

**Query Parameters:**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| date | string | N | today | 대상 날짜 |

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "uuid",
    "date": "2026-04-16",
    "generated_at": "2026-04-16T10:00:00Z",
    "briefing": {
      "headline": "오늘의 핵심 브리핑 제목",
      "summary": "역피라미드 구조의 종합 브리핑 본문...",
      "sections": [
        {
          "category": "politics",
          "title": "섹션 제목",
          "content": "해당 분야 브리핑 내용"
        }
      ]
    },
    "model_used": "claude-sonnet-4-6-20250514",
    "prompt_tokens": 2500,
    "completion_tokens": 1200
  }
}
```

### 3-2. 브리핑 리포트 수동 생성
```
POST /reports/briefing/generate
```

**Response:** 3-1과 동일 구조 (새로 생성된 리포트)

---

## 4. 기사 작성 보조 (Headlines)

### 4-1. 헤드라인 추천
```
POST /headlines/recommend
```

**Request Body:**
```json
{
  "topic": "이슈 주제 또는 키워드",
  "article_ids": ["uuid1", "uuid2"],
  "style": "neutral"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "topic": "요청 주제",
    "generated_at": "2026-04-16T10:40:00Z",
    "headlines": [
      {
        "headline": "추천 제목 1",
        "reason": "이 제목을 추천하는 이유",
        "tone": "informative"
      },
      {
        "headline": "추천 제목 2",
        "reason": "이 제목을 추천하는 이유",
        "tone": "analytical"
      },
      {
        "headline": "추천 제목 3",
        "reason": "이 제목을 추천하는 이유",
        "tone": "engaging"
      }
    ]
  }
}
```

### 4-2. 배경 타임라인
```
POST /headlines/timeline
```

**Request Body:**
```json
{
  "topic": "이슈 주제",
  "article_ids": ["uuid1", "uuid2"]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "topic": "요청 주제",
    "generated_at": "2026-04-16T10:42:00Z",
    "timeline": [
      {
        "date": "2026-01-15",
        "event": "과거 관련 사건 설명",
        "significance": "이 사건의 중요성/맥락"
      },
      {
        "date": "2026-03-20",
        "event": "후속 사건 설명",
        "significance": "현재 이슈와의 연관성"
      }
    ],
    "context_summary": "이 이슈의 전체적인 맥락 요약"
  }
}
```

---

## 5. 실시간 업데이트 (SSE)

### 5-1. 이벤트 스트림
```
GET /sse/stream
```

**Event Types:**
```
event: new_articles
data: { "count": 5, "latest_title": "최신 기사 제목" }

event: analysis_complete
data: { "type": "agenda", "date": "2026-04-16" }

event: report_generated
data: { "type": "briefing", "id": "uuid" }
```

---

## 6. 시스템 (System)

### 6-1. 헬스 체크
```
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "connected",
  "scheduler": "running",
  "last_collection": "2026-04-16T09:45:00Z"
}
```

### 6-2. 스케줄러 상태
```
GET /system/scheduler
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "running": true,
    "interval_minutes": 15,
    "next_run": "2026-04-16T10:00:00Z",
    "last_run": "2026-04-16T09:45:00Z",
    "total_collections": 42
  }
}
```

---

## DB 스키마 (참고)

### articles
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기사 고유 ID |
| title | VARCHAR(500) | 기사 제목 |
| description | TEXT | 기사 요약 |
| content | TEXT | 기사 본문 |
| url | VARCHAR(1000) UNIQUE | 기사 URL |
| source_name | VARCHAR(100) | 매체명 |
| source_type | VARCHAR(20) | domestic / foreign |
| source_api | VARCHAR(20) | newsapi / naver / rss |
| published_at | TIMESTAMP | 기사 발행 시각 |
| collected_at | TIMESTAMP | 수집 시각 |
| created_at | TIMESTAMP | DB 저장 시각 |

### article_analyses
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 분석 고유 ID |
| article_id | UUID (FK) | 기사 ID |
| category | VARCHAR(30) | 분류 카테고리 |
| keywords | JSONB | 키워드 리스트 |
| entities | JSONB | 엔티티 리스트 [{name, type}] |
| sentiment | VARCHAR(20) | positive / negative / neutral |
| importance_score | FLOAT | 중요도 (1~10) |
| analyzed_at | TIMESTAMP | 분석 시각 |
| model_used | VARCHAR(50) | 사용 모델명 |

### agenda_reports
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 리포트 ID |
| date | DATE | 대상 날짜 |
| top_issues | JSONB | Top N 이슈 데이터 |
| analysis_summary | TEXT | 종합 분석 텍스트 |
| generated_at | TIMESTAMP | 생성 시각 |
| model_used | VARCHAR(50) | 사용 모델명 |
| prompt_tokens | INT | 프롬프트 토큰 수 |
| completion_tokens | INT | 응답 토큰 수 |

### perspective_reports
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 리포트 ID |
| topic | VARCHAR(200) | 비교 주제 |
| date | DATE | 대상 날짜 |
| domestic_analysis | JSONB | 국내 관점 분석 |
| foreign_analysis | JSONB | 외신 관점 분석 |
| comparison | JSONB | 비교 분석 |
| generated_at | TIMESTAMP | 생성 시각 |
| model_used | VARCHAR(50) | 사용 모델명 |

### briefing_reports
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 리포트 ID |
| date | DATE | 대상 날짜 |
| headline | VARCHAR(200) | 브리핑 헤드라인 |
| summary | TEXT | 종합 브리핑 본문 |
| sections | JSONB | 카테고리별 섹션 |
| generated_at | TIMESTAMP | 생성 시각 |
| model_used | VARCHAR(50) | 사용 모델명 |
| prompt_tokens | INT | 프롬프트 토큰 수 |
| completion_tokens | INT | 응답 토큰 수 |

### headline_recommendations
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 추천 ID |
| topic | VARCHAR(200) | 주제 |
| headlines | JSONB | 추천 헤드라인 3선 |
| timeline | JSONB | 배경 타임라인 |
| context_summary | TEXT | 맥락 요약 |
| generated_at | TIMESTAMP | 생성 시각 |
| model_used | VARCHAR(50) | 사용 모델명 |
