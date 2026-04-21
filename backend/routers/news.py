"""뉴스 조회/검색/수집 API"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.database import get_db
from backend.database.models import Article, ArticleAnalysis
from backend.models.schemas import (
    APIResponse,
    ArticleOut,
    CollectRequest,
    CollectResult,
    Meta,
)
from backend.collectors.service import collect_all

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=APIResponse)
async def list_news(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: str | None = None,
    sentiment: str | None = None,
    source_type: str | None = None,
    sort_by: str = Query(
        "importance",
        pattern="^(importance|published_at|created_at|collected_at)$",
    ),
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """뉴스 목록 조회"""
    stmt = select(Article).options(joinedload(Article.analysis))

    # 필터
    if category:
        stmt = stmt.join(ArticleAnalysis).where(ArticleAnalysis.category == category)
    if sentiment:
        if not category:
            stmt = stmt.join(ArticleAnalysis)
        stmt = stmt.where(ArticleAnalysis.sentiment == sentiment)
    if source_type:
        stmt = stmt.where(Article.source_type == source_type)
    if q:
        stmt = stmt.where(
            or_(Article.title.ilike(f"%{q}%"), Article.description.ilike(f"%{q}%"))
        )

    # 정렬
    if sort_by == "importance":
        if not category and not sentiment:
            stmt = stmt.outerjoin(ArticleAnalysis)
        stmt = stmt.order_by(ArticleAnalysis.importance_score.desc().nullslast())
    elif sort_by == "published_at":
        stmt = stmt.order_by(Article.published_at.desc().nullslast())
    elif sort_by == "collected_at":
        stmt = stmt.order_by(Article.collected_at.desc())
    else:
        stmt = stmt.order_by(Article.created_at.desc())

    # 전체 개수
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 페이지네이션
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    articles = result.unique().scalars().all()

    return APIResponse(
        data=[ArticleOut.model_validate(a) for a in articles],
        meta=Meta(total=total, page=page, limit=limit),
    )


@router.get("/{news_id}", response_model=APIResponse)
async def get_news(news_id: UUID, db: AsyncSession = Depends(get_db)):
    """뉴스 상세 조회"""
    stmt = select(Article).options(joinedload(Article.analysis)).where(Article.id == news_id)
    result = await db.execute(stmt)
    article = result.unique().scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    return APIResponse(data=ArticleOut.model_validate(article))


@router.post("/collect", response_model=APIResponse)
async def trigger_collect(
    req: CollectRequest,
    db: AsyncSession = Depends(get_db),
):
    """수동 뉴스 수집 트리거"""
    result = await collect_all(db, sources=req.sources, query=req.query)
    return APIResponse(data=CollectResult(**result))
