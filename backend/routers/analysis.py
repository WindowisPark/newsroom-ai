"""분석 결과 API - 의제 설정, 관점 비교, 트렌드"""

import time
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

# ── /trends TTL 캐시 ──
# /trends 는 매 호출마다 풀 스캔 + 집계라 반복 요청 시 DB 부하가 큼.
# 5분 TTL 인메모리 캐시로 감소. 대시보드가 같은 period/type 을 자주 호출하는
# 패턴이라 hit 률이 높다.
_TRENDS_CACHE_TTL = 300
_trends_cache: dict[tuple[str, str], tuple[float, TrendOut]] = {}


@router.get("/agenda", response_model=APIResponse)
async def get_agenda(
    date_str: str | None = Query(None, alias="date"),
    top_n: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
):
    """의제 설정 분석 조회 (없으면 새로 생성).

    date 파라미터 미지정 시: 오늘 분석이 없으면 가장 최근 AgendaReport 를 반환.
    이렇게 해야 새벽·재기동 직후처럼 오늘자 분석이 아직 없을 때도 기자가
    대시보드에서 바로 직전 의제를 확인할 수 있다.
    """
    explicit_date = date_str is not None
    target_date = _parse_date(date_str)

    # 해당 날짜의 가장 최신 리포트 조회
    stmt = (
        select(AgendaReport)
        .where(AgendaReport.date == target_date)
        .order_by(AgendaReport.generated_at.desc())
        .limit(1)
    )
    report = (await db.execute(stmt)).scalar_one_or_none()

    if not report:
        try:
            report = await analyze_agenda(db, target_date, top_n)
        except ValueError:
            # date 미지정 시 최신 리포트로 폴백 (명시 요청 시엔 404 유지)
            if explicit_date:
                raise HTTPException(status_code=404, detail="no agenda for given date")
            fallback_stmt = (
                select(AgendaReport).order_by(AgendaReport.date.desc()).limit(1)
            )
            report = (await db.execute(fallback_stmt)).scalar_one_or_none()
            if not report:
                raise HTTPException(status_code=404, detail="no agenda available yet")

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
    """트렌드 분석 (DB 집계 기반, 5분 TTL 캐시)"""
    cache_key = (period, type)
    cached = _trends_cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < _TRENDS_CACHE_TTL:
        return APIResponse(data=cached[1])

    now = datetime.now(timezone.utc)
    hours_map = {"6h": 6, "12h": 12, "24h": 24, "7d": 168}
    since = now - timedelta(hours=hours_map[period])
    bucket = _bucket_for_period(period)  # 6h/12h/24h → hour, 7d → day

    if type == "keyword":
        data_points = await _keyword_trends(db, since, bucket)
    elif type == "category":
        data_points = await _category_trends(db, since, bucket)
    else:
        data_points = await _sentiment_trends(db, since, bucket)

    payload = TrendOut(period=period, type=type, data_points=data_points)
    _trends_cache[cache_key] = (time.monotonic(), payload)
    return APIResponse(data=payload)


def _bucket_expr(bucket: str, dialect_name: str):
    """`Article.collected_at` 을 시간·일 단위로 잘라내는 dialect-aware 표현식.

    Postgres 는 date_trunc, SQLite 는 strftime 으로 분기. 반환 표현식을
    SELECT/GROUP BY 에 공통으로 사용.
    """
    if dialect_name == "postgresql":
        unit = "hour" if bucket == "hour" else "day"
        return func.date_trunc(unit, Article.collected_at)
    # SQLite 테스트 호환 — strftime 문자열 반환 (ISO-like 정렬 가능)
    fmt = "%Y-%m-%d %H:00" if bucket == "hour" else "%Y-%m-%d"
    return func.strftime(fmt, Article.collected_at)


def _bucket_for_period(period: str) -> str:
    """6h/12h/24h → 'hour', 7d → 'day'."""
    return "day" if period == "7d" else "hour"


def _as_datetime(value) -> datetime:
    """bucket 컬럼 결과(datetime 또는 strftime 문자열)를 datetime 으로 정규화."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        # strftime 결과: "YYYY-MM-DD HH:00" 또는 "YYYY-MM-DD"
        try:
            if len(value) > 10:
                return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


async def _keyword_trends(
    db: AsyncSession, since: datetime, bucket: str
) -> list[TrendSeries]:
    """키워드 × 시간버킷 빈도. 상위 10 키워드만 반환."""
    dialect_name = db.bind.dialect.name if db.bind else "postgresql"
    bucket_col = _bucket_expr(bucket, dialect_name).label("bucket")

    stmt = (
        select(bucket_col, ArticleAnalysis.keywords)
        .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
        .where(Article.collected_at >= since)
    )
    rows = (await db.execute(stmt)).all()

    # (키워드, 버킷) 별 카운트 + 키워드 전체 합
    per_bucket: dict[str, dict[datetime, int]] = {}
    totals: dict[str, int] = {}
    for bucket_val, keywords in rows:
        if not isinstance(keywords, list):
            continue
        bucket_dt = _as_datetime(bucket_val)
        for kw in keywords:
            per_bucket.setdefault(kw, {})
            per_bucket[kw][bucket_dt] = per_bucket[kw].get(bucket_dt, 0) + 1
            totals[kw] = totals.get(kw, 0) + 1

    top_keywords = [kw for kw, _ in sorted(totals.items(), key=lambda x: x[1], reverse=True)[:10]]

    series: list[TrendSeries] = []
    for kw in top_keywords:
        points = sorted(per_bucket[kw].items())
        series.append(
            TrendSeries(
                label=kw,
                values=[TrendDataPoint(time=t, count=c) for t, c in points],
            )
        )
    return series


async def _group_by_bucket(
    db: AsyncSession, since: datetime, bucket: str, label_col
) -> list[TrendSeries]:
    """category/sentiment 공통 — (레이블, 버킷) GROUP BY → 레이블별 시리즈."""
    dialect_name = db.bind.dialect.name if db.bind else "postgresql"
    bucket_col = _bucket_expr(bucket, dialect_name).label("bucket")

    stmt = (
        select(label_col, bucket_col, func.count().label("cnt"))
        .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
        .where(Article.collected_at >= since)
        .group_by(label_col, bucket_col)
    )
    rows = (await db.execute(stmt)).all()

    per_label: dict[str, list[tuple[datetime, int]]] = {}
    for label, bucket_val, cnt in rows:
        if label is None:
            continue
        per_label.setdefault(label, []).append((_as_datetime(bucket_val), int(cnt)))

    return [
        TrendSeries(
            label=label,
            values=[TrendDataPoint(time=t, count=c) for t, c in sorted(points)],
        )
        for label, points in per_label.items()
    ]


async def _category_trends(db: AsyncSession, since: datetime, bucket: str) -> list[TrendSeries]:
    """카테고리 × 시간버킷 기사 수."""
    return await _group_by_bucket(db, since, bucket, ArticleAnalysis.category)


async def _sentiment_trends(db: AsyncSession, since: datetime, bucket: str) -> list[TrendSeries]:
    """감성 × 시간버킷 기사 수."""
    return await _group_by_bucket(db, since, bucket, ArticleAnalysis.sentiment)


def _parse_date(date_str: str | None) -> date:
    if date_str:
        return date.fromisoformat(date_str)
    return date.today()
