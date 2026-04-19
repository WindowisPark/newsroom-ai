"""API 엔드포인트 통합 테스트 - TestClient + SQLite DB"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from backend.tests.conftest import insert_article, insert_article_with_analysis


# ── Health / System ──

@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["database"] == "connected"


@pytest.mark.asyncio
async def test_scheduler_status(client):
    resp = await client.get("/api/v1/system/scheduler")
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data["data"]


# ── News: 목록 / 상세 / 수집 ──

@pytest.mark.asyncio
async def test_뉴스_목록_빈_결과(client):
    resp = await client.get("/api/v1/news")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"] == []
    assert data["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_뉴스_목록_데이터_있음(client, db_session):
    await insert_article_with_analysis(db_session, title="정치 기사", category="politics")
    await insert_article_with_analysis(db_session, title="경제 기사", category="economy")

    resp = await client.get("/api/v1/news")
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 2
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_뉴스_카테고리_필터(client, db_session):
    await insert_article_with_analysis(db_session, title="정치 기사", category="politics")
    await insert_article_with_analysis(db_session, title="경제 기사", category="economy")

    resp = await client.get("/api/v1/news?category=politics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 1
    assert data["data"][0]["title"] == "정치 기사"


@pytest.mark.asyncio
async def test_뉴스_감성_필터(client, db_session):
    await insert_article_with_analysis(db_session, title="긍정 기사", sentiment="positive")
    await insert_article_with_analysis(db_session, title="부정 기사", sentiment="negative")

    resp = await client.get("/api/v1/news?sentiment=positive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_뉴스_키워드_검색(client, db_session):
    await insert_article(db_session, title="AI 관련 기사")
    await insert_article(db_session, title="스포츠 기사")

    resp = await client.get("/api/v1/news?q=AI")
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 1
    assert "AI" in data["data"][0]["title"]


@pytest.mark.asyncio
async def test_뉴스_페이지네이션(client, db_session):
    for i in range(5):
        await insert_article(db_session, title=f"기사 {i}")

    resp = await client.get("/api/v1/news?page=1&limit=2&sort_by=created_at")
    data = resp.json()
    assert data["meta"]["total"] == 5
    assert len(data["data"]) == 2
    assert data["meta"]["page"] == 1
    assert data["meta"]["limit"] == 2


@pytest.mark.asyncio
async def test_뉴스_상세_조회(client, db_session):
    article = await insert_article_with_analysis(db_session, title="상세 기사")

    resp = await client.get(f"/api/v1/news/{article.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["title"] == "상세 기사"
    assert data["data"]["analysis"]["category"] == "politics"


@pytest.mark.asyncio
async def test_뉴스_상세_없는_ID(client):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/news/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_뉴스_수동_수집(client):
    """수집 API가 외부 API를 호출하고 결과를 반환하는지 테스트"""
    mock_result = {
        "collected_count": 10,
        "new_count": 8,
        "duplicate_count": 2,
        "sources": {"newsapi": 5, "naver": 3, "rss": 2},
    }
    with patch("backend.routers.news.collect_all", new_callable=AsyncMock, return_value=mock_result):
        resp = await client.post("/api/v1/news/collect", json={"sources": ["newsapi"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["new_count"] == 8


# ── News: 정렬 ──

@pytest.mark.asyncio
async def test_뉴스_최신순_정렬(client, db_session):
    from datetime import datetime, timezone, timedelta
    t1 = datetime(2026, 4, 15, tzinfo=timezone.utc)
    t2 = datetime(2026, 4, 16, tzinfo=timezone.utc)

    await insert_article(db_session, title="어제 기사", published_at=t1)
    await insert_article(db_session, title="오늘 기사", published_at=t2)

    resp = await client.get("/api/v1/news?sort_by=published_at")
    data = resp.json()
    assert data["data"][0]["title"] == "오늘 기사"


# ── Analysis: 트렌드 ──

@pytest.mark.asyncio
async def test_트렌드_빈_결과(client):
    resp = await client.get("/api/v1/analysis/trends?period=24h&type=keyword")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["period"] == "24h"
    assert data["data"]["type"] == "keyword"


@pytest.mark.asyncio
async def test_트렌드_카테고리(client, db_session):
    await insert_article_with_analysis(db_session, category="politics")
    await insert_article_with_analysis(db_session, category="economy")

    resp = await client.get("/api/v1/analysis/trends?period=24h&type=category")
    assert resp.status_code == 200
    data = resp.json()
    labels = [dp["label"] for dp in data["data"]["data_points"]]
    assert "politics" in labels


@pytest.mark.asyncio
async def test_트렌드_잘못된_기간(client):
    resp = await client.get("/api/v1/analysis/trends?period=99h")
    assert resp.status_code == 422  # validation error


# ── Analysis: 의제 ──

@pytest.mark.asyncio
async def test_의제_분석_mock(client, db_session):
    """LLM을 mock하여 의제 분석 생성 테스트"""
    await insert_article_with_analysis(db_session, title="정치 이슈 기사", category="politics")

    mock_llm_response = {
        "content": {
            "top_issues": [
                {
                    "rank": 1,
                    "topic": "테스트 이슈",
                    "summary": "테스트 요약",
                    "importance_score": 9.0,
                    "trend": "rising",
                    "categories": ["politics"],
                    "key_keywords": ["테스트"],
                }
            ],
            "analysis_summary": "종합 분석",
        },
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "model_used": "test-model",
    }

    from datetime import datetime, timezone
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with patch("backend.analyzers.agenda.call_llm", new_callable=AsyncMock, return_value=mock_llm_response):
        resp = await client.get(f"/api/v1/analysis/agenda?date={today_utc}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]["top_issues"]) == 1
        assert data["data"]["top_issues"][0]["topic"] == "테스트 이슈"


# ── Drafts ──

@pytest.mark.asyncio
async def test_초안_생성_mock(client, db_session):
    """LLM을 mock하여 초안 생성 테스트"""
    article = await insert_article(db_session, title="호르무즈 해협 봉쇄")

    mock_llm_response = {
        "content": {
            "title_candidates": ["호르무즈 봉쇄", "중동 긴장 고조", "해협 봉쇄 파장"],
            "lead": "이란이 호르무즈 해협을 봉쇄했다.",
            "body": "자세한 본문 Markdown",
            "background": "배경 설명",
            "six_w_check": {"who": "이란", "what": "호르무즈 봉쇄"},
            "sources": [],
        },
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "model_used": "claude-sonnet-4-6",
    }

    with patch("backend.analyzers.drafter.call_llm", new_callable=AsyncMock, return_value=mock_llm_response):
        resp = await client.post(
            "/api/v1/drafts/generate",
            json={"article_ids": [str(article.id)], "style": "straight"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]["title_candidates"]) == 3
        # 빈 sources는 입력 기사에서 자동 채움
        assert len(data["data"]["sources"]) == 1
        assert data["data"]["sources"][0]["name"] == "테스트뉴스"


@pytest.mark.asyncio
async def test_초안_빈_article_ids_거부(client):
    resp = await client.post("/api/v1/drafts/generate", json={"article_ids": []})
    assert resp.status_code == 422  # pydantic min_length=1


@pytest.mark.asyncio
async def test_초안_존재하지_않는_기사(client):
    resp = await client.post(
        "/api/v1/drafts/generate",
        json={"article_ids": [str(uuid.uuid4())]},
    )
    assert resp.status_code == 404


# ── Watchlist ──

@pytest.mark.asyncio
async def test_워치리스트_목록_빈(client):
    resp = await client.get("/api/v1/watchlist")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_워치리스트_추가_조회(client):
    resp = await client.post("/api/v1/watchlist", json={"keyword": "호르무즈"})
    assert resp.status_code == 200
    item = resp.json()["data"]
    assert item["keyword"] == "호르무즈"
    assert item["is_active"] is True
    assert item["match_count"] == 0

    resp2 = await client.get("/api/v1/watchlist")
    assert len(resp2.json()["data"]) == 1


@pytest.mark.asyncio
async def test_워치리스트_중복_409(client):
    await client.post("/api/v1/watchlist", json={"keyword": "환율"})
    resp = await client.post("/api/v1/watchlist", json={"keyword": "환율"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_워치리스트_활성_토글(client):
    created = (await client.post("/api/v1/watchlist", json={"keyword": "금리"})).json()["data"]
    resp = await client.patch(f"/api/v1/watchlist/{created['id']}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_워치리스트_삭제(client):
    created = (await client.post("/api/v1/watchlist", json={"keyword": "AI"})).json()["data"]
    resp = await client.delete(f"/api/v1/watchlist/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True

    resp_list = await client.get("/api/v1/watchlist")
    assert resp_list.json()["data"] == []


@pytest.mark.asyncio
async def test_워치리스트_존재하지_않는_id_404(client):
    resp = await client.delete(f"/api/v1/watchlist/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── Article Drafts (예비 기사) ──

_ARTICLE_DRAFT_PAYLOAD = {
    "title": "미·이란 협상 급물살",
    "lead": "미국과 이란이 협상 테이블로 복귀했다.",
    "body": "본문 내용입니다.",
    "background": "중동 긴장 완화 맥락.",
    "category": "world",
    "style": "straight",
    "six_w_check": {"who": "미국과 이란"},
    "sources": [{"name": "CNN", "url": "https://cnn.com/1"}],
    "references": [{"name": "서울신문", "url": "https://seoul.co.kr/1"}],
    "background_sources": [],
    "origin_article_ids": [],
}


@pytest.mark.asyncio
async def test_예비기사_저장_조회(client):
    resp = await client.post("/api/v1/article-drafts", json=_ARTICLE_DRAFT_PAYLOAD)
    assert resp.status_code == 200
    created = resp.json()["data"]
    assert created["status"] == "draft"
    assert created["title"] == "미·이란 협상 급물살"
    assert len(created["references"]) == 1

    list_resp = await client.get("/api/v1/article-drafts")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) == 1

    detail = await client.get(f"/api/v1/article-drafts/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["lead"] == "미국과 이란이 협상 테이블로 복귀했다."


@pytest.mark.asyncio
async def test_예비기사_편집(client):
    created = (await client.post("/api/v1/article-drafts", json=_ARTICLE_DRAFT_PAYLOAD)).json()["data"]
    resp = await client.patch(
        f"/api/v1/article-drafts/{created['id']}",
        json={"title": "제목 수정됨"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "제목 수정됨"


@pytest.mark.asyncio
async def test_예비기사_상태_전이_draft_to_review_to_approved(client):
    created = (await client.post("/api/v1/article-drafts", json=_ARTICLE_DRAFT_PAYLOAD)).json()["data"]
    draft_id = created["id"]

    # draft → in_review
    r1 = await client.post(
        f"/api/v1/article-drafts/{draft_id}/transition",
        json={"to": "in_review"},
    )
    assert r1.status_code == 200
    assert r1.json()["data"]["status"] == "in_review"
    assert r1.json()["data"]["submitted_at"] is not None

    # in_review → approved
    r2 = await client.post(
        f"/api/v1/article-drafts/{draft_id}/transition",
        json={"to": "approved", "note": "LGTM"},
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "approved"
    assert r2.json()["data"]["review_note"] == "LGTM"
    assert r2.json()["data"]["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_예비기사_잘못된_전이_409(client):
    created = (await client.post("/api/v1/article-drafts", json=_ARTICLE_DRAFT_PAYLOAD)).json()["data"]
    # draft → approved 는 허용 안 됨 (in_review 거쳐야 함)
    resp = await client.post(
        f"/api/v1/article-drafts/{created['id']}/transition",
        json={"to": "approved"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_예비기사_in_review_상태에서_편집_거부(client):
    created = (await client.post("/api/v1/article-drafts", json=_ARTICLE_DRAFT_PAYLOAD)).json()["data"]
    await client.post(
        f"/api/v1/article-drafts/{created['id']}/transition", json={"to": "in_review"}
    )
    resp = await client.patch(
        f"/api/v1/article-drafts/{created['id']}", json={"title": "편집 시도"}
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_예비기사_삭제(client):
    created = (await client.post("/api/v1/article-drafts", json=_ARTICLE_DRAFT_PAYLOAD)).json()["data"]
    resp = await client.delete(f"/api/v1/article-drafts/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True


@pytest.mark.asyncio
async def test_예비기사_상태_필터(client):
    d1 = (await client.post("/api/v1/article-drafts", json=_ARTICLE_DRAFT_PAYLOAD)).json()["data"]
    d2 = (await client.post("/api/v1/article-drafts", json=_ARTICLE_DRAFT_PAYLOAD)).json()["data"]
    await client.post(f"/api/v1/article-drafts/{d1['id']}/transition", json={"to": "in_review"})

    drafts_only = await client.get("/api/v1/article-drafts?status=draft")
    assert len(drafts_only.json()["data"]) == 1
    assert drafts_only.json()["data"][0]["id"] == d2["id"]

    reviews = await client.get("/api/v1/article-drafts?status=in_review")
    assert len(reviews.json()["data"]) == 1
    assert reviews.json()["data"][0]["id"] == d1["id"]
