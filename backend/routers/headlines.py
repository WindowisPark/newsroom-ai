"""기사 작성 보조 API - 헤드라인 추천 + 배경 타임라인"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.schemas import (
    APIResponse,
    HeadlineRequest,
    HeadlineOut,
    TimelineRequest,
    TimelineOut,
)
from backend.analyzers.headline import recommend_headlines, generate_timeline

router = APIRouter(prefix="/headlines", tags=["headlines"])


@router.post("/recommend", response_model=APIResponse)
async def headline_recommend(
    req: HeadlineRequest,
    db: AsyncSession = Depends(get_db),
):
    """헤드라인 추천 3선"""
    result = await recommend_headlines(db, req.topic, req.article_ids, req.style)

    return APIResponse(data=HeadlineOut(
        topic=result["topic"],
        generated_at=result["generated_at"],
        headlines=result.get("headlines", []),
    ))


@router.post("/timeline", response_model=APIResponse)
async def headline_timeline(
    req: TimelineRequest,
    db: AsyncSession = Depends(get_db),
):
    """배경 타임라인 생성"""
    result = await generate_timeline(db, req.topic, req.article_ids)

    return APIResponse(data=TimelineOut(
        topic=result["topic"],
        generated_at=result["generated_at"],
        timeline=result.get("timeline", []),
        context_summary=result.get("context_summary", ""),
    ))
