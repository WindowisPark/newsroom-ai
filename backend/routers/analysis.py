"""분석 결과 API - 의제 설정, 관점 비교, 트렌드"""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.database.models import AgendaReport, ArticleAnalysis, Article
from backend.models.schemas import APIResponse, AgendaOut, PerspectiveOut, TrendOut, TrendSeries, TrendDataPoint
from backend.analyzers.agenda import analyze_agenda
from backend.analyzers.perspective import compare_perspectives

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/agenda", response_model=APIResponse)
async def get_agenda(
    date_str: str | None = Query(None, alias="date"),
    top_n: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
):
    """의제 설정 분석 조회 (없으면 새로 생성)"""
    target_date = _parse_date(date_str)

    # 기존 리포트 조회
    stmt = (
        select(AgendaReport)
        .where(AgendaReport.date == target_date)
        .order_by(AgendaReport.generated_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        try:
            report = await analyze_agenda(db, target_date, top_n)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return APIResponse(data=AgendaOut(
        date=report.date,
        generated_at=report.generated_at,
        top_issues=report.top_issues,
        analysis_summary=report.analysis_summary or "",
    ))


@router.get("/perspective", response_model=APIResponse)
async def get_perspective(
    topic: str = Query(..., min_length=1),
    date_str: str | None = Query(None, alias="date"),
    db: AsyncSession = Depends(get_db),
):
    """관점 비교 분석"""
    target_date = _parse_date(date_str)

    try:
        report = await compare_perspectives(db, topic, target_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return APIResponse(data={
        "topic": report.topic,
        "generated_at": report.generated_at,
        "domestic": report.domestic_analysis,
        "foreign": report.foreign_analysis,
        "comparison": report.comparison,
    })


@router.get("/trends", response_model=APIResponse)
async def get_trends(
    period: str = Query("24h", pattern="^(6h|12h|24h|7d)$"),
    type: str = Query("keyword", pattern="^(keyword|category|sentiment)$"),
    db: AsyncSession = Depends(get_db),
):
    """트렌드 분석 (DB 집계 기반)"""
    now = datetime.now(timezone.utc)
    hours_map = {"6h": 6, "12h": 12, "24h": 24, "7d": 168}
    since = now - timedelta(hours=hours_map[period])

    if type == "keyword":
        data_points = await _keyword_trends(db, since)
    elif type == "category":
        data_points = await _category_trends(db, since)
    else:
        data_points = await _sentiment_trends(db, since)

    return APIResponse(data=TrendOut(period=period, type=type, data_points=data_points))


async def _keyword_trends(db: AsyncSession, since: datetime) -> list[TrendSeries]:
    """키워드 빈도 트렌드"""
    stmt = (
        select(ArticleAnalysis.keywords, func.count().label("cnt"))
        .join(Article, Article.id == ArticleAnalysis.article_id)
        .where(Article.collected_at >= since)
        .group_by(ArticleAnalysis.keywords)
    )
    result = await db.execute(stmt)
    # 키워드별 집계
    keyword_counts: dict[str, int] = {}
    for row in result.all():
        keywords = row[0] if isinstance(row[0], list) else []
        count = row[1]
        for kw in keywords:
            keyword_counts[kw] = keyword_counts.get(kw, 0) + count

    # 상위 10개
    top = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return [
        TrendSeries(
            label=kw,
            values=[TrendDataPoint(time=datetime.now(timezone.utc), count=cnt)],
        )
        for kw, cnt in top
    ]


async def _category_trends(db: AsyncSession, since: datetime) -> list[TrendSeries]:
    """카테고리별 기사 수 트렌드"""
    stmt = (
        select(ArticleAnalysis.category, func.count().label("cnt"))
        .join(Article, Article.id == ArticleAnalysis.article_id)
        .where(Article.collected_at >= since)
        .group_by(ArticleAnalysis.category)
    )
    result = await db.execute(stmt)
    return [
        TrendSeries(
            label=row[0],
            values=[TrendDataPoint(time=datetime.now(timezone.utc), count=row[1])],
        )
        for row in result.all()
    ]


async def _sentiment_trends(db: AsyncSession, since: datetime) -> list[TrendSeries]:
    """감성별 기사 수 트렌드"""
    stmt = (
        select(ArticleAnalysis.sentiment, func.count().label("cnt"))
        .join(Article, Article.id == ArticleAnalysis.article_id)
        .where(Article.collected_at >= since)
        .group_by(ArticleAnalysis.sentiment)
    )
    result = await db.execute(stmt)
    return [
        TrendSeries(
            label=row[0],
            values=[TrendDataPoint(time=datetime.now(timezone.utc), count=row[1])],
        )
        for row in result.all()
    ]


def _parse_date(date_str: str | None) -> date:
    if date_str:
        return date.fromisoformat(date_str)
    return date.today()
