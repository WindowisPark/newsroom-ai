"""E2E 파이프라인 테스트 - 수집 → 분석 → 자동 보고 전체 흐름"""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.database.models import Article, ArticleAnalysis, BriefingReport, AgendaReport
from backend.tests.conftest import insert_article, insert_article_with_analysis


# ── 수집 파이프라인 ──

@pytest.mark.asyncio
async def test_수집_중복제거_파이프라인(db_session):
    """같은 URL의 기사는 중복 저장되지 않아야 함"""
    from backend.collectors.service import _save_articles

    articles = [
        {"title": "기사 1", "url": "https://test.com/1", "source_name": "A", "source_type": "domestic", "source_api": "naver"},
        {"title": "기사 2", "url": "https://test.com/2", "source_name": "B", "source_type": "foreign", "source_api": "newsapi"},
        {"title": "기사 1 중복", "url": "https://test.com/1", "source_name": "A", "source_type": "domestic", "source_api": "naver"},
    ]

    saved = await _save_articles(db_session, articles)
    assert saved == 2  # 중복 1건 제거

    # 같은 데이터로 다시 저장 시도
    saved2 = await _save_articles(db_session, articles)
    assert saved2 == 0  # 전부 이미 존재


@pytest.mark.asyncio
async def test_수집_빈_리스트(db_session):
    from backend.collectors.service import _save_articles

    saved = await _save_articles(db_session, [])
    assert saved == 0


@pytest.mark.asyncio
async def test_수집_통합_서비스_mock(db_session):
    """collect_all이 외부 API를 호출하고 결과를 올바르게 집계하는지 테스트"""
    from backend.collectors.service import collect_all

    mock_articles = [
        {"title": "NewsAPI 기사", "url": "https://newsapi.com/1", "source_name": "CNN",
         "source_type": "foreign", "source_api": "newsapi", "published_at": datetime.now(timezone.utc)},
    ]

    with patch("backend.collectors.service.newsapi.fetch_top_headlines", new_callable=AsyncMock, return_value=mock_articles), \
         patch("backend.collectors.service.naver.fetch_by_categories", new_callable=AsyncMock, return_value=[]), \
         patch("backend.collectors.service.rss.fetch_feeds", new_callable=AsyncMock, return_value=[]):

        result = await collect_all(db_session)
        assert result["collected_count"] == 1
        assert result["new_count"] == 1
        assert result["duplicate_count"] == 0
        assert result["sources"]["newsapi"] == 1


# ── 분석 파이프라인 ──

@pytest.mark.asyncio
async def test_분류_배치_mock(db_session):
    """classify_batch가 기사를 분류하고 DB에 저장하는지 테스트"""
    from backend.analyzers.classifier import classify_batch

    article = await insert_article(db_session, title="분류 테스트 기사")

    mock_llm = {
        "content": {
            "category": "politics",
            "keywords": ["정치", "테스트"],
            "entities": [{"name": "테스트인", "type": "person"}],
            "sentiment": "neutral",
            "importance_score": 7.0,
        },
        "prompt_tokens": 50,
        "completion_tokens": 100,
        "model_used": "test-haiku",
    }

    with patch("backend.analyzers.classifier.call_llm", new_callable=AsyncMock, return_value=mock_llm):
        results = await classify_batch([article], db_session)
        assert len(results) == 1
        assert results[0].category == "politics"
        assert results[0].sentiment == "neutral"

    # DB에 저장 확인
    stmt = select(ArticleAnalysis).where(ArticleAnalysis.article_id == article.id)
    db_result = await db_session.execute(stmt)
    analysis = db_result.scalar_one_or_none()
    assert analysis is not None
    assert analysis.category == "politics"


# ── 자동 보고 파이프라인 ──

@pytest.mark.asyncio
async def test_자동_브리핑_생성(db_session):
    """충분한 기사가 있으면 브리핑이 자동 생성되는지 테스트"""
    from backend.analyzers.reporter import generate_briefing

    # 분석 완료된 기사 5건 삽입
    for i in range(5):
        await insert_article_with_analysis(
            db_session,
            title=f"브리핑용 기사 {i}",
            category="politics" if i % 2 == 0 else "economy",
            importance_score=8.0 - i * 0.5,
        )

    mock_llm = {
        "content": {
            "headline": "오늘의 핵심 브리핑",
            "summary": "종합 브리핑 내용",
            "sections": [
                {"category": "politics", "title": "정치 브리핑", "content": "정치 관련 내용"},
                {"category": "economy", "title": "경제 브리핑", "content": "경제 관련 내용"},
            ],
        },
        "prompt_tokens": 500,
        "completion_tokens": 300,
        "model_used": "test-sonnet",
    }

    with patch("backend.analyzers.reporter.call_llm", new_callable=AsyncMock, return_value=mock_llm):
        report = await generate_briefing(db_session, date.today())
        assert report.headline == "오늘의 핵심 브리핑"
        assert len(report.sections) == 2

    # DB에 저장 확인
    stmt = select(BriefingReport).where(BriefingReport.date == date.today())
    result = await db_session.execute(stmt)
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.headline == "오늘의 핵심 브리핑"


@pytest.mark.asyncio
async def test_자동_보고_최소_기사수_미달(db_session):
    """기사 수가 부족하면 자동 보고를 건너뛰는지 테스트"""
    from backend.scheduler import _auto_generate_reports

    # 기사 2건만 삽입 (기본 최소 5건)
    for i in range(2):
        await insert_article_with_analysis(db_session, title=f"기사 {i}")

    with patch("backend.analyzers.reporter.generate_briefing", new_callable=AsyncMock) as mock_briefing, \
         patch("backend.analyzers.agenda.analyze_agenda", new_callable=AsyncMock) as mock_agenda:
        await _auto_generate_reports(db_session)
        mock_briefing.assert_not_called()
        mock_agenda.assert_not_called()


@pytest.mark.asyncio
async def test_자동_보고_이미_존재하면_건너뜀(db_session):
    """오늘 보고가 이미 존재하면 다시 생성하지 않는지 테스트"""
    from backend.scheduler import _auto_generate_reports

    # 충분한 기사 삽입
    for i in range(6):
        await insert_article_with_analysis(db_session, title=f"기사 {i}")

    # 이미 브리핑+의제 존재
    db_session.add(BriefingReport(
        date=date.today(), headline="기존 브리핑", model_used="test",
    ))
    db_session.add(AgendaReport(
        date=date.today(), top_issues=[], model_used="test",
    ))
    await db_session.commit()

    with patch("backend.analyzers.reporter.generate_briefing", new_callable=AsyncMock) as mock_briefing, \
         patch("backend.analyzers.agenda.analyze_agenda", new_callable=AsyncMock) as mock_agenda, \
         patch("backend.routers.sse.broadcast_event"):
        await _auto_generate_reports(db_session)
        mock_briefing.assert_not_called()
        mock_agenda.assert_not_called()


# ── 전체 E2E: 수집 → 분류 → 자동 보고 ──

@pytest.mark.asyncio
async def test_전체_파이프라인_e2e(db_session):
    """collection_pipeline 전체 흐름을 mock 외부 API로 테스트"""
    from backend.scheduler import collection_pipeline

    mock_collect_result = {
        "collected_count": 6,
        "new_count": 6,
        "duplicate_count": 0,
        "sources": {"newsapi": 3, "naver": 3},
    }

    mock_classify_result = {
        "content": {
            "category": "politics", "keywords": ["테스트"],
            "entities": [], "sentiment": "neutral", "importance_score": 7.0,
        },
        "prompt_tokens": 50, "completion_tokens": 100, "model_used": "test",
    }

    mock_briefing_result = {
        "content": {
            "headline": "E2E 브리핑", "summary": "E2E 테스트",
            "sections": [{"category": "politics", "title": "정치", "content": "내용"}],
        },
        "prompt_tokens": 500, "completion_tokens": 300, "model_used": "test-sonnet",
    }

    mock_agenda_result = {
        "content": {
            "top_issues": [{"rank": 1, "topic": "E2E 이슈", "summary": "요약",
                           "importance_score": 9.0, "trend": "rising",
                           "categories": ["politics"], "key_keywords": ["테스트"]}],
            "analysis_summary": "분석",
        },
        "prompt_tokens": 200, "completion_tokens": 200, "model_used": "test-sonnet",
    }

    # 수집할 기사 6건 미리 DB에 삽입 (collect_all을 mock)
    articles = []
    for i in range(6):
        a = await insert_article(db_session, title=f"E2E 기사 {i}")
        articles.append(a)

    with patch("backend.scheduler.collect_all", new_callable=AsyncMock, return_value=mock_collect_result), \
         patch("backend.scheduler.classify_batch", new_callable=AsyncMock, return_value=[]), \
         patch("backend.scheduler.broadcast_event"), \
         patch("backend.scheduler.async_session") as mock_session_factory, \
         patch("backend.scheduler._auto_generate_reports", new_callable=AsyncMock):

        # async context manager mock
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        await collection_pipeline()

    # 스케줄러 통계 확인
    from backend.scheduler import _stats
    assert _stats["total_collections"] > 0
    assert _stats["last_run"] is not None
