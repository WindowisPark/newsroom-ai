"""대시보드 전용 통계 API - 단일 호출로 핵심 메트릭 반환"""

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.database.models import Article, ArticleAnalysis
from backend.models.schemas import APIResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=APIResponse)
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """오늘의 대시보드 핵심 메트릭"""
    today = date.today()

    # 오늘 수집 기사 수
    total_stmt = (
        select(func.count())
        .select_from(Article)
        .where(func.date(Article.collected_at) == today)
    )
    total_articles = (await db.execute(total_stmt)).scalar() or 0

    # 미분석 기사 수
    unanalyzed_stmt = (
        select(func.count())
        .select_from(Article)
        .outerjoin(ArticleAnalysis)
        .where(ArticleAnalysis.id.is_(None))
    )
    unanalyzed_count = (await db.execute(unanalyzed_stmt)).scalar() or 0

    # 중요도 8+ 기사 수
    high_stmt = (
        select(func.count())
        .select_from(ArticleAnalysis)
        .join(Article)
        .where(
            func.date(Article.collected_at) == today,
            ArticleAnalysis.importance_score >= 8.0,
        )
    )
    high_importance_count = (await db.execute(high_stmt)).scalar() or 0

    # 속보급 (9+)
    breaking_stmt = (
        select(func.count())
        .select_from(ArticleAnalysis)
        .join(Article)
        .where(
            func.date(Article.collected_at) == today,
            ArticleAnalysis.importance_score >= 9.0,
        )
    )
    breaking_count = (await db.execute(breaking_stmt)).scalar() or 0

    # 상위 키워드 (오늘)
    kw_stmt = (
        select(ArticleAnalysis.keywords)
        .join(Article)
        .where(func.date(Article.collected_at) == today)
    )
    kw_result = await db.execute(kw_stmt)
    keyword_counter: Counter = Counter()
    for (keywords,) in kw_result.all():
        if isinstance(keywords, list):
            for kw in keywords:
                keyword_counter[kw] += 1
    top_keywords = [
        {"keyword": kw, "count": cnt}
        for kw, cnt in keyword_counter.most_common(10)
    ]

    # 카테고리 분포 (오늘)
    cat_stmt = (
        select(ArticleAnalysis.category, func.count().label("cnt"))
        .join(Article)
        .where(func.date(Article.collected_at) == today)
        .group_by(ArticleAnalysis.category)
    )
    cat_result = await db.execute(cat_stmt)
    category_distribution = {row[0]: row[1] for row in cat_result.all()}

    return APIResponse(data={
        "total_articles_today": total_articles,
        "unanalyzed_count": unanalyzed_count,
        "high_importance_count": high_importance_count,
        "breaking_count": breaking_count,
        "top_keywords": top_keywords,
        "category_distribution": category_distribution,
    })
